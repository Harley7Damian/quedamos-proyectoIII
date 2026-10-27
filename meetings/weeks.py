"""Utilidades de semanas. La coordinacion se hace sobre una semana (lunes a domingo)."""
from datetime import date, timedelta


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def default_week_start(today: date) -> date:
    """Si hoy es sabado o domingo, la semana util siguiente; si no, la semana en curso."""
    monday = monday_of(today)
    return monday + timedelta(days=7) if today.weekday() >= 5 else monday


def week_choices(today: date):
    """Opciones del formulario: esta semana y la proxima, como (fecha ISO, etiqueta)."""
    this_monday = monday_of(today)
    out = []
    for label, monday in (("Esta semana", this_monday), ("Próxima semana", this_monday + timedelta(days=7))):
        sunday = monday + timedelta(days=6)
        out.append((monday.isoformat(), f"{label} ({monday:%d/%m} al {sunday:%d/%m})"))
    return out
