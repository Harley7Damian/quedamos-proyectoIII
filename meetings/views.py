from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import User

from .forms import LinkForm, MeetingRequestForm
from .models import AssistantLink, MeetingRequest


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
