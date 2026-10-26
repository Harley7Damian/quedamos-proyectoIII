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
def rango_horario(slot):
    """Ej. '10:00 - 10:45' a partir de un ProposedSlot (usa start y end)."""
    return f"{slot.start.strftime('%H:%M')} - {slot.end.strftime('%H:%M')}"