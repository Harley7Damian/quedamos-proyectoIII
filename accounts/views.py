from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from meetings.forms import LinkForm
from meetings.models import AssistantLink
from scheduling.mock import MOCK_PROPOSAL

from .forms import AreaForm, ProtectHoursForm, SignupForm, WorkHoursForm
from .models import Profile, User


def signup(request):
    if request.user.is_authenticated:
        return redirect("panel")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("onboarding")
    return render(request, "registration/signup.html", {"form": form})


# ---------------------------------------------------------------- TR-43: onboarding de tres pasos segun el rol

STEPS = 3


def _profile(user):
    return Profile.objects.get_or_create(user=user)[0]


def _linked_executives(user):
    if user.is_executive:
        return User.objects.filter(pk=user.pk)
    return User.objects.filter(assistant_links__assistant=user)


def _data(request):
    """Datos enviados, o None si es GET. Un POST vacio tambien se valida y muestra sus errores."""
    return request.POST if request.method == "POST" else None


def _render(request, template, step, ctx, status=200):
    base = {"step": step, "steps": STEPS, "proposal": MOCK_PROPOSAL, "me": request.user}
    return render(request, template, {**base, **ctx}, status=status)


@login_required
def onboarding(request, step=1):
    """Tres pantallas, una pregunta por pantalla. Quien ya lo completo u omitio va directo al panel."""
    profile = _profile(request.user)
    if profile.onboarding_done:
        return redirect("panel")
    steps = {1: _step_area, 2: _step_work_or_link, 3: _step_protect}
    if step not in steps:
        raise Http404
    return steps[step](request, profile)


def _step_area(request, profile):
    form = AreaForm(_data(request), initial={"area": profile.area or None})
    if request.method == "POST":
        if form.is_valid():
            profile.area = form.cleaned_data["area"]
            profile.save()
            return redirect("onboarding_step", step=2)
        return _render(request, "onboarding/paso1.html", 1, {"form": form}, status=400)
    return _render(request, "onboarding/paso1.html", 1, {"form": form})


def _step_work_or_link(request, profile):
    user = request.user
    if user.is_executive:
        form = WorkHoursForm(_data(request), instance=profile)
        if request.method == "POST":
            if form.is_valid():
                form.save()
                return redirect("onboarding_step", step=3)
            return _render(request, "onboarding/paso2_ejecutivo.html", 2, {"form": form}, status=400)
        return _render(request, "onboarding/paso2_ejecutivo.html", 2, {"form": form})

    # Asistente: se vincula con su ejecutivo usando el codigo de 6 caracteres.
    form = LinkForm(_data(request))
    error = None
    if request.method == "POST":
        if form.is_valid():
            executive = User.objects.filter(role=User.Role.EJECUTIVO, link_code=form.cleaned_data["code"]).first()
            if executive is not None:
                AssistantLink.objects.get_or_create(assistant=user, executive=executive)
                messages.success(request, f"Quedaste vinculada con {executive.full_name}.")
                return redirect("onboarding_step", step=3)
            error = "Ese código no existe. Revisa que esté bien escrito."
        else:
            error = "Escribe el código de 6 caracteres."
    ctx = {"form": form, "error": error, "executives": _linked_executives(user)}
    return _render(request, "onboarding/paso2_asistente.html", 2, ctx, status=400 if error else 200)


def _step_protect(request, profile):
    user = request.user
    executives = _linked_executives(user)
    if not executives.exists():
        # Asistente sin vinculo: sin ejecutivo no hay a quien proteger horarios.
        profile.onboarding_completed_at = timezone.now()
        profile.save()
        messages.info(request, "Para proteger horarios primero vincúlate con un ejecutivo desde el panel. Luego podrás crear las reglas aquí.")
        return redirect("rules")
    form = ProtectHoursForm(_data(request), user=user, executives=executives)
    if request.method == "POST":
        if form.is_valid():
            created = form.save()
            profile.onboarding_completed_at = timezone.now()
            profile.save()
            done = f"Configuración lista. Se crearon {created} reglas de horarios protegidos." if created != 1 else \
                "Configuración lista. Se creó 1 regla de horarios protegidos."
            if user.is_executive:
                messages.success(request, f"{done} Tu código de vinculación es {user.link_code}: compártelo con tu asistente.")
                return redirect(reverse("panel") + "#vinculacion")
            messages.success(request, done)
            return redirect("panel")
        return _render(request, "onboarding/paso3.html", 3, {"form": form}, status=400)
    return _render(request, "onboarding/paso3.html", 3, {"form": form})


@login_required
@require_POST
def skip_onboarding(request):
    profile = _profile(request.user)
    if not profile.onboarding_done:
        profile.onboarding_skipped_at = timezone.now()
        profile.save()
        messages.info(request, "Puedes configurar tus horarios protegidos cuando quieras desde Reglas.")
    return redirect("panel")
