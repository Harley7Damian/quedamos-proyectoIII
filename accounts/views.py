import json
import re
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from meetings.forms import LinkForm
from meetings.models import AssistantLink
from scheduling.mock import MOCK_PROPOSAL

from .forms import AreaForm, ProtectHoursForm, SignupForm, WorkHoursForm
from .models import Profile, User, generate_link_code
from .telegram import enviar_mensaje_telegram


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

# ---------------------------------------------------------------- TR-73: vinculación de Telegram

@login_required
@require_POST
def telegram_generar_codigo(request):
    profile = _profile(request.user)
    profile.telegram_link_code = generate_link_code()
    profile.telegram_link_code_expira_en = timezone.now() + timedelta(minutes=settings.TELEGRAM_LINK_CODE_MINUTES)
    profile.save()
    messages.success(
        request,
        f"Tu código para vincular Telegram es {profile.telegram_link_code}. "
        f"Envíaselo al bot con /vincular {profile.telegram_link_code} antes de "
        f"{settings.TELEGRAM_LINK_CODE_MINUTES} minutos.",
    )
    return redirect("panel")


@login_required
@require_POST
def telegram_desvincular(request):
    profile = _profile(request.user)
    profile.telegram_chat_id = None
    profile.telegram_vinculado_en = None
    profile.save()
    messages.info(request, "Desvinculaste tu cuenta de Telegram.")
    return redirect("panel")



VINCULAR_RE = re.compile(r"^/(?:vincular|start)\s+([A-Za-z0-9]+)")


@csrf_exempt
@require_POST
def telegram_webhook(request):
    """Recibe los mensajes que le escriben al bot de Telegram. Siempre responde 200 para que Telegram no reintente."""
    secreto_esperado = settings.TELEGRAM_WEBHOOK_SECRET
    if secreto_esperado and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != secreto_esperado:
        return HttpResponse(status=403)
    
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return HttpResponse(status=400)

    message = data.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    texto = message.get("text", "")

    if chat_id is None or not texto:
        return HttpResponse(status=200)

    match = VINCULAR_RE.match(texto.strip())
    if not match:
        return HttpResponse(status=200)

    code = match.group(1).upper()
    profile = Profile.objects.filter(
        telegram_link_code=code,
        telegram_link_code_expira_en__gt=timezone.now(),
    ).first()

    if profile is None:
        enviar_mensaje_telegram(str(chat_id), "Ese código no es válido o ya expiró. Genera uno nuevo desde Quedamos.")
        return HttpResponse(status=200)

    profile.telegram_chat_id = str(chat_id)
    profile.telegram_vinculado_en = timezone.now()
    profile.telegram_link_code = None
    profile.telegram_link_code_expira_en = None
    profile.save()

    enviar_mensaje_telegram(str(chat_id), "¡Listo! Tu cuenta de Quedamos quedó vinculada a Telegram. Te avisaremos antes de tus reuniones.")
    return HttpResponse(status=200)

def ejecutar_recordatorios(request):
    secreto = request.GET.get("secreto", "")
    if secreto != settings.TAREAS_SECRET or not settings.TAREAS_SECRET:
        return HttpResponseForbidden("No autorizado")
    call_command("enviar_recordatorios")
    return HttpResponse("ok")
