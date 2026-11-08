"""Reglas de horarios protegidos de un ejecutivo (HU-07). Lógica pura, sin base de datos.

Una regla bloquea una franja horaria, todos los días o solo uno. Ejemplos:
- RuleSpec(None, 0, 10): nada antes de las 10:00.
- RuleSpec(4, 0, 24): el viernes completo está protegido.
- RuleSpec(None, 13, 14): sin reuniones durante el almuerzo.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .matching import format_end_hour, format_hour

DAY_NAMES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
DAY_PLURALS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábados", "domingos"]


def _hours(dt: datetime) -> float:
    return dt.hour + dt.minute / 60


@dataclass(frozen=True)
class RuleSpec:
    weekday: int | None  # 0 es lunes; None aplica todos los días
    start_hour: int  # 0 a 23
    end_hour: int  # 1 a 24

    def applies_on(self, start: datetime) -> bool:
        return self.weekday is None or start.weekday() == self.weekday

    def blocks(self, start: datetime, end: datetime) -> bool:
        """True si la reunión (start a end, mismo día) cae, aunque sea en parte, dentro de la franja protegida."""
        if not self.applies_on(start):
            return False
        return _hours(start) < self.end_hour and self.start_hour < _hours(end)

    @property
    def label(self) -> str:
        if self.start_hour == 0 and self.end_hour == 24:
            return f"{DAY_NAMES[self.weekday]} protegido"
        if self.start_hour == 0:
            text = f"nada antes de las {format_hour(self.end_hour)}"
        elif self.end_hour == 24:
            text = f"nada desde las {format_hour(self.start_hour)}"
        else:
            text = f"sin reuniones de {format_hour(self.start_hour)} a {format_hour(self.end_hour)}"
        if self.weekday is not None:
            text += f" los {DAY_PLURALS[self.weekday]}"
        return text

    @property
    def range_text(self) -> str:
        """Franja con las dos horas explicitas, por ejemplo 'Desde 18:00 hasta el fin del día'."""
        return f"Desde {format_hour(self.start_hour)} hasta {format_end_hour(self.end_hour)}"


def validate_rule(weekday, start_hour: int, end_hour: int) -> str | None:
    """Mensaje de error, o None si la regla es válida."""
    if not (0 <= start_hour <= 23 and 1 <= end_hour <= 24):
        return "Las horas deben estar entre 00:00 y el fin del día."
    if start_hour >= end_hour:
        return "La hora de inicio debe ser menor que la de fin."
    if weekday is not None and not (0 <= weekday <= 6):
        return "El día no es válido."
    if weekday is None and start_hour == 0 and end_hour == 24:
        return "Esa regla bloquearía todos los horarios de todos los días. Elige un día o una franja."
    return None
