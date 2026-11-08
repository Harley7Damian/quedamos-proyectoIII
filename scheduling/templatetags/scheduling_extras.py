from django import template

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