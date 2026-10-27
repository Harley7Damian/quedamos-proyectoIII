from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User
from scheduling.proposal import build_proposal

from .forms import LinkForm, MeetingRequestForm, SchedulingRuleForm
from .grid import grid_rows, parse_blocks, week_header
from .links import ExpiredLink, InvalidLink, make_token, read_token
from .models import AssistantLink, Availability, MeetingRequest, SchedulingRule


def _executives_of(user):
    """Ejecutivos a los que puede atender la persona: sus vinculos (asistente) o ella misma (ejecutivo)."""
    if user.is_executive:
        return User.objects.filter(pk=user.pk)
    return User.objects.filter(assistant_links__assistant=user)


def _links_of(user):
    """Vinculos de la persona con el otro lado (asistentes de un ejecutivo, o ejecutivos de una asistente)."""
    if user.is_executive:
        return AssistantLink.objects.filter(executive=user).select_related("assistant")
    return AssistantLink.objects.filter(assistant=user).select_related("executive")


def _requests_context(user):
    return {"requests": MeetingRequest.objects.visible_to(user).select_related("executive", "created_by")}


@login_required
def panel(request):
    user = request.user
    ctx = {"me": user, **_requests_context(user), "links": _links_of(user)}
    if not user.is_executive:
        executives = _executives_of(user)
        ctx["link_form"] = LinkForm()
        ctx["request_form"] = MeetingRequestForm(user=user, executives=executives)
    return render(request, "panel/panel.html", ctx)


@login_required
def request_list(request):
    """Fragmento que el panel recarga solo cada pocos segundos (HTMX)."""
    return render(request, "panel/_request_list.html", _requests_context(request.user))


@login_required
@require_POST
def link_executive(request):
    user = request.user
    if not user.is_assistant:
        raise PermissionDenied("Solo las asistentes pueden vincularse con un código.")
    form = LinkForm(request.POST)
    if form.is_valid():
        executive = User.objects.filter(role=User.Role.EJECUTIVO, link_code=form.cleaned_data["code"]).first()
        if executive is None:
            messages.error(request, "Ese código no existe. Revisa que esté bien escrito.")
        else:
            _, created = AssistantLink.objects.get_or_create(assistant=user, executive=executive)
            messages.success(request, f"Quedaste vinculada con {executive.full_name}." if created else f"Ya estabas vinculada con {executive.full_name}.")
    else:
        messages.error(request, "Escribe el código de 6 caracteres.")
    return redirect("panel")


@login_required
@require_POST
def unlink(request, pk):
    link = get_object_or_404(AssistantLink, pk=pk)
    if request.user.pk not in (link.assistant_id, link.executive_id):
        raise PermissionDenied
    link.delete()
    messages.success(request, "Vínculo eliminado.")
    return redirect("panel")


@login_required
@require_POST
def create_request(request):
    user = request.user
    form = MeetingRequestForm(request.POST, user=user, executives=_executives_of(user))
    if form.is_valid():
        with transaction.atomic():
            form.save()
        messages.success(request, "Solicitud creada.")
        return redirect("panel")
    # Se vuelve a mostrar el panel con los errores del formulario.
    ctx = {"me": user, "links": _links_of(user), "link_form": LinkForm(), "request_form": form, **_requests_context(user)}
    return render(request, "panel/panel.html", ctx, status=400)


# ---------------------------------------------------------------- HU-05: detalle y enlace para la contraparte


def _visible_request_or_404(user, pk):
    """404 tanto si no existe como si no es visible: no se revela que existe."""
    return get_object_or_404(MeetingRequest.objects.visible_to(user).select_related("executive", "created_by"), pk=pk)


def _availability_of(meeting_request, party):
    return meeting_request.availabilities.filter(party=party).first()


RULES_BLOCK = (
    "Hay horarios en que coinciden las dos partes, pero las reglas protegidas del ejecutivo los descartan. "
    "Revisa las reglas o amplía el rango marcando más horarios."
)
NO_MATCH = (
    "No hay un horario en que coincidan las dos partes para esta duración. "
    "Amplía el rango: marca más horarios, o crea la solicitud para otra semana."
)


def _active_rules(meeting_request):
    return SchedulingRule.objects.filter(executive=meeting_request.executive_id, active=True)


def _proposal_for(meeting_request, executive, counterpart, rules=None):
    """Propuesta calculada con la disponibilidad guardada de ambas partes y las reglas activas del ejecutivo."""
    if rules is None:
        rules = [rule.spec() for rule in _active_rules(meeting_request)]
    return build_proposal(
        request_id=meeting_request.pk,
        title=meeting_request.title,
        executive_name=meeting_request.executive.full_name,
        counterpart_name=meeting_request.counterpart_name,
        duration_min=meeting_request.duration_min,
        week_start=meeting_request.effective_week_start,
        executive_blocks=executive.blocks,
        counterpart_blocks=counterpart.blocks,
        now=timezone.now(),
        tz=timezone.get_current_timezone(),
        rules=rules,
    )


def _no_match_message(meeting_request, executive, counterpart):
    """Si sin reglas habría opciones, el problema son las reglas y no la falta de coincidencia."""
    if _active_rules(meeting_request).exists() and _proposal_for(meeting_request, executive, counterpart, rules=[]).slots:
        return RULES_BLOCK
    return NO_MATCH


def _detail_context(user, meeting_request, link=None):
    executive = _availability_of(meeting_request, Availability.Party.EJECUTIVO)
    counterpart = _availability_of(meeting_request, Availability.Party.CONTRAPARTE)
    proposal = None
    if executive and counterpart and meeting_request.status == MeetingRequest.Status.PROPUESTA:
        proposal = _proposal_for(meeting_request, executive, counterpart)
    return {
        "me": user,
        "r": meeting_request,
        "executive_av": executive,
        "counterpart": counterpart,
        "counterpart_count": len(counterpart.blocks) if counterpart else 0,
        "days": week_header(meeting_request.effective_week_start),
        "rows": grid_rows(executive.blocks if executive else {}),
        "can_generate": bool(executive and counterpart) and meeting_request.accepts_availability,
        "proposal": proposal,
        "no_match": _no_match_message(meeting_request, executive, counterpart) if proposal is not None and not proposal.slots else None,
        "active_rules": [rule.label for rule in _active_rules(meeting_request)],
        "link": link,
        "link_days": settings.COUNTERPART_LINK_MAX_AGE // 86400,
    }


@login_required
def request_detail(request, pk):
    meeting_request = _visible_request_or_404(request.user, pk)
    return render(request, "panel/request_detail.html", _detail_context(request.user, meeting_request))


@login_required
@require_POST
def create_counterpart_link(request, pk):
    meeting_request = _visible_request_or_404(request.user, pk)
    if not meeting_request.accepts_availability:
        messages.error(request, "Esta solicitud ya no recibe disponibilidad.")
        return redirect("request_detail", pk=pk)
    url = request.build_absolute_uri(reverse("public_availability", args=[make_token(meeting_request.pk)]))
    link = {"url": url, "expires": timezone.now() + timedelta(seconds=settings.COUNTERPART_LINK_MAX_AGE)}
    return render(request, "panel/request_detail.html", _detail_context(request.user, meeting_request, link))


@login_required
@require_POST
def save_executive_availability(request, pk):
    meeting_request = _visible_request_or_404(request.user, pk)
    if not meeting_request.accepts_availability:
        messages.error(request, "Esta solicitud ya no recibe disponibilidad.")
        return redirect("request_detail", pk=pk)
    blocks = parse_blocks(request.POST)
    if not blocks:
        messages.error(request, "Marca al menos un horario en que el ejecutivo pueda reunirse.")
        return redirect("request_detail", pk=pk)
    Availability.objects.update_or_create(
        request=meeting_request, party=Availability.Party.EJECUTIVO, defaults={"blocks": blocks}
    )
    messages.success(request, "Guardamos la disponibilidad del ejecutivo.")
    return redirect("request_detail", pk=pk)


@login_required
@require_POST
def generate_proposal(request, pk):
    meeting_request = _visible_request_or_404(request.user, pk)
    if not meeting_request.accepts_availability:
        messages.error(request, "Esta solicitud ya no recibe propuestas.")
        return redirect("request_detail", pk=pk)
    executive = _availability_of(meeting_request, Availability.Party.EJECUTIVO)
    counterpart = _availability_of(meeting_request, Availability.Party.CONTRAPARTE)
    if not executive or not counterpart:
        faltan = "la del ejecutivo" if not executive else "la de la contraparte"
        messages.error(request, f"Falta la disponibilidad de ambas partes: aún no está {faltan}.")
        return redirect("request_detail", pk=pk)
    proposal = _proposal_for(meeting_request, executive, counterpart)
    if proposal.slots:
        meeting_request.status = MeetingRequest.Status.PROPUESTA
        messages.success(request, "Propuesta generada.")
    else:
        meeting_request.status = MeetingRequest.Status.PENDIENTE
        messages.error(request, _no_match_message(meeting_request, executive, counterpart))
    meeting_request.save(update_fields=["status"])
    return redirect("request_detail", pk=pk)


def _public_response(request, template, ctx, status=200):
    response = render(request, template, ctx, status=status)
    # El enlace lleva un secreto en la URL: que no viaje en el encabezado Referer hacia otros sitios ni lo indexen buscadores. same-origin y no no-referrer, porque este ultimo hace que el navegador envie Origin: null y Django rechaza el formulario.
    response["Referrer-Policy"] = "same-origin"
    response["X-Robots-Tag"] = "noindex"
    return response


def public_availability(request, token):
    """Pagina publica (sin cuenta) donde la contraparte marca su disponibilidad. Solo muestra el asunto."""
    try:
        request_id = read_token(token)
    except ExpiredLink:
        return _public_response(request, "public/enlace_invalido.html", {"expired": True}, status=410)
    except InvalidLink:
        return _public_response(request, "public/enlace_invalido.html", {"expired": False}, status=404)

    meeting_request = MeetingRequest.objects.filter(pk=request_id).first()
    if meeting_request is None:
        return _public_response(request, "public/enlace_invalido.html", {"expired": False}, status=404)
    if not meeting_request.accepts_availability:
        return _public_response(request, "public/enlace_invalido.html", {"closed": True}, status=410)

    existing = _availability_of(meeting_request, Availability.Party.CONTRAPARTE)
    blocks = existing.blocks if existing else {}
    error = None
    if request.method == "POST":
        blocks = parse_blocks(request.POST)
        if blocks:
            Availability.objects.update_or_create(
                request=meeting_request, party=Availability.Party.CONTRAPARTE, defaults={"blocks": blocks}
            )
            messages.success(request, "Listo, registramos tu disponibilidad. Puedes volver a abrir este enlace para cambiarla.")
            return redirect(request.path)
        error = "Marca al menos un horario en el que puedas reunirte."

    ctx = {
        "title": meeting_request.title,
        "duration": meeting_request.duration_min,
        "days": week_header(meeting_request.effective_week_start),
        "rows": grid_rows(blocks),
        "answered": existing is not None,
        "error": error,
    }
    return _public_response(request, "public/disponibilidad.html", ctx, status=400 if error else 200)


# ---------------------------------------------------------------- HU-07: reglas del ejecutivo (horarios protegidos)


def _rules_of(user):
    return SchedulingRule.objects.filter(executive__in=_executives_of(user)).select_related("executive")


def _rules_context(user, form=None):
    return {"me": user, "rules": _rules_of(user), "form": form or SchedulingRuleForm(user=user, executives=_executives_of(user))}


@login_required
def rules(request):
    return render(request, "panel/rules.html", _rules_context(request.user))


@login_required
@require_POST
def create_rule(request):
    user = request.user
    form = SchedulingRuleForm(request.POST, user=user, executives=_executives_of(user))
    if form.is_valid():
        form.save()
        messages.success(request, "Regla guardada.")
        return redirect("rules")
    return render(request, "panel/rules.html", _rules_context(user, form), status=400)


@login_required
def edit_rule(request, pk):
    user = request.user
    rule = get_object_or_404(_rules_of(user), pk=pk)
    if request.method == "POST":
        form = SchedulingRuleForm(request.POST, instance=rule, user=user, executives=_executives_of(user))
        if form.is_valid():
            form.save()
            messages.success(request, "Regla actualizada.")
            return redirect("rules")
        return render(request, "panel/rule_edit.html", {"rule": rule, "form": form}, status=400)
    form = SchedulingRuleForm(instance=rule, user=user, executives=_executives_of(user))
    return render(request, "panel/rule_edit.html", {"rule": rule, "form": form})


@login_required
@require_POST
def toggle_rule(request, pk):
    rule = get_object_or_404(_rules_of(request.user), pk=pk)
    rule.active = not rule.active
    rule.save(update_fields=["active"])
    messages.success(request, "Regla activada." if rule.active else "Regla desactivada.")
    return redirect("rules")
