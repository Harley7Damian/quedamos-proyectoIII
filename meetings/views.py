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

from .forms import LinkForm, MeetingRequestForm
from .grid import grid_rows, parse_blocks, week_header
from .links import ExpiredLink, InvalidLink, make_token, read_token
from .models import AssistantLink, Availability, MeetingRequest


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


def _detail_context(user, meeting_request, link=None):
    counterpart = _availability_of(meeting_request, Availability.Party.CONTRAPARTE)
    return {
        "me": user,
        "r": meeting_request,
        "counterpart": counterpart,
        "counterpart_count": len(counterpart.blocks) if counterpart else 0,
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
