from types import SimpleNamespace

from django import template
from django.utils import timezone

register = template.Library()

_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


@register.filter
def fecha_larga(value):
    """Ej. 'martes, 27 de octubre' a partir de un datetime."""
    return f"{_DIAS[value.weekday()]}, {value.day} de {_MESES[value.month - 1]}"


@register.filter
def duracion(value):
    """Ej. '2 d 3 h', '4 h 5 min' o '12 min' a partir de un timedelta."""
    total = int(value.total_seconds())
    days, rest = divmod(total, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        return f"{days} d {hours} h"
    if hours:
        return f"{hours} h {minutes} min"
    if minutes:
        return f"{minutes} min"
    return "menos de 1 min"


@register.filter
def rango_horario(slot):
    """Ej. '10:00 - 10:45' a partir de un ProposedSlot (usa start y end)."""
    return f"{slot.start.strftime('%H:%M')} - {slot.end.strftime('%H:%M')}"


@register.filter
def estado_visible(solicitud):
    """TR-58: estado que ve la persona (clave de color e icono, etiqueta y ayuda corta) segun el avance de la solicitud."""
    estado = solicitud.status
    if estado == "aprobada":
        return SimpleNamespace(clave="aprobada", etiqueta="Aprobada", ayuda="El ejecutivo ya eligió un horario")
    if estado == "cancelada":
        return SimpleNamespace(clave="cancelada", etiqueta="Cancelada", ayuda="La solicitud se canceló")
    if solicitud.new_options_requested_at:
        return SimpleNamespace(clave="otras", etiqueta="Pidió otras opciones", ayuda="Hay que generar una nueva propuesta")
    if estado == "propuesta":
        return SimpleNamespace(clave="propuesta", etiqueta="Propuesta lista", ayuda="Falta que el ejecutivo apruebe una opción")
    respondio = getattr(solicitud, "contraparte_respondio", None)
    if respondio is None:
        respondio = solicitud.availabilities.filter(party="contraparte").exists()
    if respondio:
        return SimpleNamespace(clave="respondio", etiqueta="Contraparte respondió", ayuda="Ya se puede generar la propuesta")
    return SimpleNamespace(clave="pendiente", etiqueta="Pendiente", ayuda="Falta la disponibilidad de la contraparte")


@register.filter
def horario_aprobado(solicitud):
    """Horario aprobado en hora local (para mostrarlo en la lista), o None si aun no esta aprobado."""
    if solicitud.status != "aprobada" or not solicitud.approved_start or not solicitud.approved_end:
        return None
    return SimpleNamespace(start=timezone.localtime(solicitud.approved_start), end=timezone.localtime(solicitud.approved_end))
