"""Contenido de los recordatorios de reunión por Telegram (TR-75)."""
from django.conf import settings
from django.urls import reverse
from django.utils import timezone


def _hora(dt) -> str:
    return timezone.localtime(dt).strftime("%H:%M")


def _enlace_panel() -> str:
    return f"{settings.SITE_URL}{reverse('panel')}"


def mensaje_recordatorio_30(meeting_request) -> str:
    """Primer aviso, 30 minutos antes de la reunión."""
    return (
        f"⏰ En 30 min: reunión con {meeting_request.counterpart_name} "
        f"({meeting_request.title}) a las {_hora(meeting_request.approved_start)}.\n"
        "Responde /visto para confirmarlo.\n"
        f"Ver en Quedamos: {_enlace_panel()}"
    )


def mensaje_recordatorio_5(meeting_request) -> str:
    """Segundo aviso, 5 minutos antes de la reunión. Mas urgente, sin sonar alarmante."""
    return (
        f"🚨 En 5 min: reunión con {meeting_request.counterpart_name} "
        f"({meeting_request.title}) a las {_hora(meeting_request.approved_start)}.\n"
        "Responde /visto si todavía no lo hiciste.\n"
        f"Ver en Quedamos: {_enlace_panel()}"
    )
