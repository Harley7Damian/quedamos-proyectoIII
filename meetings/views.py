from datetime import timedelta
from functools import wraps
from types import SimpleNamespace

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import F
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_safe

from accounts.models import User
from scheduling.proposal import build_proposal

from .calendar_import import ICSError, decode_ics, free_blocks, parse_ics, week_window
from .forms import LinkForm, MeetingRequestForm, SchedulingRuleForm
from .grid import grid_rows, parse_blocks, week_header
from .ics import build_ics
from .metrics import BASELINE_MESSAGES, meeting_metric, summarize
from .links import ExpiredLink, InvalidLink, make_approval_token, make_token, read_approval_token, read_token
from .models import AssistantLink, Availability, MeetingRequest, SchedulingRule


def assistant_required(view):
    """TR-48: la coordinacion la opera la asistente. El ejecutivo ve el estado y aprueba con su enlace."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_assistant:
            raise PermissionDenied("Esta acción corresponde a la asistente.")
        return view(request, *args, **kwargs)
    return wrapper


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
@assistant_required
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


def _approved_slot(meeting_request):
    """Opcion aprobada con las horas en la zona horaria local (para mostrarla), o None."""
    if not meeting_request.is_approved:
        return None
    return SimpleNamespace(
        start=timezone.localtime(meeting_request.approved_start), end=timezone.localtime(meeting_request.approved_end)
    )


def _detail_context(user, meeting_request, link=None, approval_link=None):
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
        "approval_link": approval_link,
        "approved": _approved_slot(meeting_request),
    }


@login_required
def request_detail(request, pk):
    meeting_request = _visible_request_or_404(request.user, pk)
    return render(request, "panel/request_detail.html", _detail_context(request.user, meeting_request))


@login_required
@require_POST
@assistant_required
def create_counterpart_link(request, pk):
    meeting_request = _visible_request_or_404(request.user, pk)
    if not meeting_request.accepts_availability:
        messages.error(request, "Esta solicitud ya no recibe disponibilidad.")
        return redirect("request_detail", pk=pk)
    url = request.build_absolute_uri(reverse("public_availability", args=[make_token(meeting_request.pk)]))
    MeetingRequest.objects.filter(pk=meeting_request.pk).update(links_shared=F("links_shared") + 1)
    link = {"url": url, "expires": timezone.now() + timedelta(seconds=settings.COUNTERPART_LINK_MAX_AGE)}
    return render(request, "panel/request_detail.html", _detail_context(request.user, meeting_request, link))


@login_required
@require_POST
@assistant_required
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
@assistant_required
def import_executive_calendar(request, pk):
    """TR-14: calcula la disponibilidad del ejecutivo desde un archivo .ics. El archivo se lee en memoria y no se guarda."""
    meeting_request = _visible_request_or_404(request.user, pk)
    if not meeting_request.accepts_availability:
        messages.error(request, "Esta solicitud ya no recibe disponibilidad.")
        return redirect("request_detail", pk=pk)
    archivo = request.FILES.get("archivo")
    if archivo is None:
        messages.error(request, "Elige un archivo de calendario (.ics) para importar.")
        return redirect("request_detail", pk=pk)
    try:
        if not archivo.name.lower().endswith(".ics"):
            raise ICSError("El archivo debe tener la extensión .ics.")
        tz = timezone.get_current_timezone()
        week_start = meeting_request.effective_week_start
        window_start, window_end = week_window(week_start, tz)
        result = parse_ics(decode_ics(archivo.read(settings.ICS_MAX_BYTES + 1)), tz, window_start, window_end)
    except ICSError as error:
        messages.error(request, str(error))
        return redirect("request_detail", pk=pk)
    blocks = free_blocks(result.busy, week_start, tz)
    if not blocks:
        messages.error(
            request,
            "Con ese calendario no queda ningún horario libre de lunes a viernes entre las 08:00 y las 22:00. "
            "No cambiamos la disponibilidad guardada.",
        )
        return redirect("request_detail", pk=pk)
    Availability.objects.update_or_create(
        request=meeting_request, party=Availability.Party.EJECUTIVO, defaults={"blocks": blocks}
    )
    messages.success(
        request,
        f"Importamos el calendario: {len(blocks)} horarios libres de lunes a viernes. "
        "Reemplazan la disponibilidad anterior. Puedes ajustarlos abajo y guardar de nuevo.",
    )
    notices = []
    if result.unsupported:
        notices.append(f"{result.unsupported} evento(s) con una repetición que no sabemos interpretar se contaron solo en su primera fecha")
    if result.skipped:
        notices.append(f"{result.skipped} evento(s) con datos ilegibles se omitieron")
    if result.unknown_zones:
        notices.append("se usó la hora de Lima para estas zonas horarias desconocidas: " + ", ".join(sorted(result.unknown_zones)))
    if notices:
        messages.warning(request, "Revisa la cuadrícula: " + "; ".join(notices) + ".")
    return redirect("request_detail", pk=pk)


@login_required
@require_POST
@assistant_required
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
        meeting_request.new_options_requested_at = None
        meeting_request.proposal_rounds = F("proposal_rounds") + 1
        messages.success(request, "Propuesta generada.")
    else:
        meeting_request.status = MeetingRequest.Status.PENDIENTE
        messages.warning(request, _no_match_message(meeting_request, executive, counterpart))
    meeting_request.save(update_fields=["status", "new_options_requested_at", "proposal_rounds"])
    return redirect("request_detail", pk=pk)


@login_required
@require_POST
@assistant_required
def create_approval_link(request, pk):
    """La asistente genera el enlace de aprobacion que se envia al ejecutivo (HU-08). Solo con una propuesta vigente."""
    meeting_request = _visible_request_or_404(request.user, pk)
    if meeting_request.status != MeetingRequest.Status.PROPUESTA:
        messages.error(request, "Primero genera una propuesta de horarios: el enlace de aprobación se crea sobre una propuesta vigente.")
        return redirect("request_detail", pk=pk)
    url = request.build_absolute_uri(reverse("public_approval", args=[make_approval_token(meeting_request.pk)]))
    MeetingRequest.objects.filter(pk=meeting_request.pk).update(links_shared=F("links_shared") + 1)
    approval_link = {
        "url": url,
        "expires": timezone.now() + timedelta(seconds=settings.APPROVAL_LINK_MAX_AGE),
        "mailto_subject": f"Aprueba tu reunión: {meeting_request.title}",
        "mailto_body": f"Hola {meeting_request.executive.full_name}, puedes aprobar el horario de la reunión aquí, sin iniciar sesión: {url}",
    }
    return render(request, "panel/request_detail.html", _detail_context(request.user, meeting_request, approval_link=approval_link))


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


# ---------------------------------------------------------------- HU-08: aprobacion en un toque (enlace firmado)


def _approval_state_response(request, meeting_request, state, proposal=None, token=None):
    ctx = {
        "state": state,
        "r": meeting_request,
        "proposal": proposal,
        "approved": _approved_slot(meeting_request),
        "token": token,
    }
    return _public_response(request, "public/aprobacion.html", ctx)


def public_approval(request, token):
    """Pagina publica (sin cuenta) donde el ejecutivo aprueba una de las opciones o pide otras con un toque."""
    try:
        request_id = read_approval_token(token)
    except ExpiredLink:
        return _public_response(request, "public/enlace_invalido.html", {"expired": True, "approval": True}, status=410)
    except InvalidLink:
        return _public_response(request, "public/enlace_invalido.html", {"expired": False}, status=404)

    meeting_request = MeetingRequest.objects.select_related("executive").filter(pk=request_id).first()
    if meeting_request is None:
        return _public_response(request, "public/enlace_invalido.html", {"expired": False}, status=404)

    if request.method == "POST":
        return _decide_approval(request, request_id, token)

    status = meeting_request.status
    if status == MeetingRequest.Status.CANCELADA:
        return _public_response(request, "public/enlace_invalido.html", {"cancelled": True}, status=410)
    if status == MeetingRequest.Status.APROBADA:
        return _approval_state_response(request, meeting_request, "approved", token=token)
    if status == MeetingRequest.Status.PENDIENTE:
        if meeting_request.new_options_requested_at:
            return _approval_state_response(request, meeting_request, "requested")
        return _public_response(request, "public/enlace_invalido.html", {"stale": True}, status=410)

    executive = _availability_of(meeting_request, Availability.Party.EJECUTIVO)
    counterpart = _availability_of(meeting_request, Availability.Party.CONTRAPARTE)
    proposal = _proposal_for(meeting_request, executive, counterpart) if executive and counterpart else None
    if proposal is None or not proposal.slots:
        return _public_response(request, "public/enlace_invalido.html", {"stale": True}, status=410)
    return _approval_state_response(request, meeting_request, "choose", proposal)


def _decide_approval(request, request_id, token):
    """Un toque: aprueba la opcion elegida o rechaza todas. Repetir el toque no cambia lo ya decidido."""
    with transaction.atomic():
        meeting_request = MeetingRequest.objects.select_for_update().select_related("executive").get(pk=request_id)
        if meeting_request.status == MeetingRequest.Status.PROPUESTA:
            if "reject" in request.POST:
                meeting_request.request_new_options()
                messages.success(request, "Listo, avisamos a la asistente que necesitas otras opciones.")
            else:
                slot_id = request.POST.get("slot", "")
                executive = _availability_of(meeting_request, Availability.Party.EJECUTIVO)
                counterpart = _availability_of(meeting_request, Availability.Party.CONTRAPARTE)
                proposal = _proposal_for(meeting_request, executive, counterpart) if executive and counterpart else None
                slot = next((s for s in proposal.slots if s.id == slot_id), None) if proposal else None
                if slot is None:
                    messages.error(request, "Esa opción ya no está disponible. Revisa las opciones vigentes.")
                else:
                    meeting_request.approve(slot.start, slot.end)
                    messages.success(request, "Listo, reunión aprobada.")
    return redirect("public_approval", token=token)


# ---------------------------------------------------------------- HU-09: confirmacion, invitacion .ics e historial


def _ics_response(meeting_request):
    response = HttpResponse(build_ics(meeting_request), content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="reunion-{meeting_request.pk}.ics"'
    return response


@login_required
@require_safe
def request_ics(request, pk):
    """La asistente (o el ejecutivo) descarga la invitacion de una reunion ya aprobada."""
    meeting_request = _visible_request_or_404(request.user, pk)
    if not meeting_request.is_approved:
        raise Http404("La reunion aun no esta aprobada.")
    return _ics_response(meeting_request)


@require_safe
def approval_ics(request, token):
    """El ejecutivo descarga la invitacion desde su enlace de aprobacion, sin iniciar sesion."""
    try:
        request_id = read_approval_token(token)
    except ExpiredLink:
        return _public_response(request, "public/enlace_invalido.html", {"expired": True, "approval": True}, status=410)
    except InvalidLink:
        return _public_response(request, "public/enlace_invalido.html", {"expired": False}, status=404)
    meeting_request = MeetingRequest.objects.select_related("executive").filter(pk=request_id).first()
    if meeting_request is None or not meeting_request.is_approved:
        return _public_response(request, "public/enlace_invalido.html", {"expired": False}, status=404)
    response = _ics_response(meeting_request)
    response["Referrer-Policy"] = "same-origin"
    response["X-Robots-Tag"] = "noindex"
    return response


@login_required
def history(request):
    """Reuniones confirmadas visibles para la persona, las mas proximas o recientes primero."""
    confirmed = (
        MeetingRequest.objects.visible_to(request.user)
        .filter(status=MeetingRequest.Status.APROBADA, approved_start__isnull=False)
        .select_related("executive")
        .order_by("-approved_start")
    )
    items = [{"r": meeting_request, "slot": _approved_slot(meeting_request)} for meeting_request in confirmed]
    return render(request, "panel/historial.html", {"me": request.user, "items": items})


# ---------------------------------------------------------------- HU-10: metricas de uso


@login_required
def metrics(request):
    """Metricas de las reuniones confirmadas visibles para la persona: lo medido y lo estimado, rotulados como tal."""
    confirmed = (
        MeetingRequest.objects.visible_to(request.user)
        .filter(status=MeetingRequest.Status.APROBADA, approved_start__isnull=False, decided_at__isnull=False)
        .select_related("executive")
        .order_by("-decided_at")
    )
    items = [meeting_metric(meeting_request) for meeting_request in confirmed]
    ctx = {"me": request.user, "items": items, "summary": summarize(items), "baseline": BASELINE_MESSAGES}
    return render(request, "panel/metricas.html", ctx)


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
