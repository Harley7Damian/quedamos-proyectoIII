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


# ---------------------------------------------------------------- Antelación configurable de los avisos

# Opciones que cada persona puede activar (minutos antes de la reunión), de la más lejana a la más cercana.
ANTELACIONES = [
    (2880, "2 días antes"),
    (1440, "1 día antes"),
    (120, "2 horas antes"),
    (60, "1 hora antes"),
    (30, "30 minutos antes"),
    (15, "15 minutos antes"),
    (5, "5 minutos antes"),
]
ANTELACIONES_VALIDAS = {minutos for minutos, _ in ANTELACIONES}
ANTELACION_MAXIMA = ANTELACIONES[0][0]
# Lo que tenía la aplicación antes de que fuera configurable: nadie nota el cambio si no toca nada.
ANTELACION_POR_DEFECTO = [30, 5]
# La llamada solo tiene sentido cerca de la reunión: no se llama dos días antes.
ANTELACION_MAXIMA_LLAMADA = 15

_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def avisos_por_defecto() -> list[int]:
    return list(ANTELACION_POR_DEFECTO)


def normalizar_antelaciones(valores) -> list[int]:
    """Devuelve las antelaciones válidas, sin repetir y de la más lejana a la más cercana."""
    limpios = set()
    for valor in valores or []:
        try:
            minutos = int(valor)
        except (TypeError, ValueError):
            continue
        if minutos in ANTELACIONES_VALIDAS:
            limpios.add(minutos)
    return sorted(limpios, reverse=True)


def _cuando(minutos: int) -> str:
    if minutos >= 1440:
        dias = minutos // 1440
        return "Mañana" if dias == 1 else f"En {dias} días"
    if minutos >= 60:
        horas = minutos // 60
        return "En 1 hora" if horas == 1 else f"En {horas} horas"
    return f"En {minutos} min"


def _fecha_hora(dt) -> str:
    local = timezone.localtime(dt)
    return f"el {_DIAS[local.weekday()]} {local:%d/%m} a las {local:%H:%M}"


def mensaje_aviso(meeting_request, minutos: int) -> str:
    """Texto de Telegram para un aviso a `minutos` de la reunión. 30 y 5 conservan su texto de siempre."""
    if minutos == 30:
        return mensaje_recordatorio_30(meeting_request)
    if minutos == 5:
        return mensaje_recordatorio_5(meeting_request)
    if minutos >= 120:
        cuando_abs = _fecha_hora(meeting_request.approved_start)
    else:
        cuando_abs = f"a las {_hora(meeting_request.approved_start)}"
    return (
        f"📅 {_cuando(minutos)}: reunión con {meeting_request.counterpart_name} "
        f"({meeting_request.title}) {cuando_abs}.\n"
        "Responde /visto para confirmarlo.\n"
        f"Ver en Quedamos: {_enlace_panel()}"
    )


_EN_PALABRAS = {5: "cinco minutos", 15: "quince minutos", 30: "treinta minutos", 60: "una hora",
                120: "dos horas", 1440: "un día", 2880: "dos días"}


def texto_llamada_recordatorio(meeting_request, minutos: int = 5) -> str:
    """Texto pensado para ser leido en voz por la llamada de Twilio (TR-85).
    Sin emojis, sin instrucciones de Telegram ni enlaces: solo lo esencial."""
    return (
        f"Hola. Te recordamos que en {_EN_PALABRAS.get(minutos, f'{minutos} minutos')} tienes una reunión en Quedamos "
        f"con {meeting_request.counterpart_name}, a las {_hora(meeting_request.approved_start)}."
    )
