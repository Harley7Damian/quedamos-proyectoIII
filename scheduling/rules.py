"""Reglas de horarios protegidos de un ejecutivo (HU-07). Lógica pura, sin base de datos.

Una regla bloquea una franja horaria, todos los días o solo uno. Ejemplos:
- RuleSpec(None, 0, 10): nada antes de las 10:00.
- RuleSpec(4, 0, 24): el viernes completo está protegido.
- RuleSpec(None, 13, 14): sin reuniones durante el almuerzo.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .matching import STEP_MIN, format_end_hour, format_time

DAY_NAMES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
DAY_PLURALS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábados", "domingos"]


def _minutes(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute


@dataclass(frozen=True)
class RuleSpec:
    weekday: int | None  # 0 es lunes; None aplica todos los días
    start_hour: int  # 0 a 23
    end_hour: int  # 1 a 24
    start_minute: int = 0  # 0, 15, 30 o 45
    end_minute: int = 0  # 0, 15, 30 o 45 (siempre 0 si la hora de fin es 24)

    @property
    def start_total(self) -> int:
        """Minutos desde las 00:00 en que empieza la franja protegida."""
        return self.start_hour * 60 + self.start_minute

    @property
    def end_total(self) -> int:
        """Minutos desde las 00:00 en que termina la franja protegida (1440 es el cierre del día)."""
        return self.end_hour * 60 + self.end_minute

    def applies_on(self, start: datetime) -> bool:
        return self.weekday is None or start.weekday() == self.weekday

    def blocks(self, start: datetime, end: datetime) -> bool:
        """True si la reunión (start a end, mismo día) cae, aunque sea en parte, dentro de la franja protegida."""
        if not self.applies_on(start):
            return False
        return _minutes(start) < self.end_total and self.start_total < _minutes(end)

    @property
    def label(self) -> str:
        if self.start_total == 0 and self.end_total == 1440:
            return f"{DAY_NAMES[self.weekday]} protegido"
        if self.start_total == 0:
            text = f"nada antes de las {format_time(self.end_hour, self.end_minute)}"
        elif self.end_total == 1440:
            text = f"nada desde las {format_time(self.start_hour, self.start_minute)}"
        else:
            text = (f"sin reuniones de {format_time(self.start_hour, self.start_minute)} "
                    f"a {format_time(self.end_hour, self.end_minute)}")
        if self.weekday is not None:
            text += f" los {DAY_PLURALS[self.weekday]}"
        return text

    @property
    def range_text(self) -> str:
        """Franja con las dos horas explicitas, por ejemplo 'Desde 18:00 hasta el fin del día'."""
        fin = format_end_hour(self.end_hour) if self.end_minute == 0 else format_time(self.end_hour, self.end_minute)
        return f"Desde {format_time(self.start_hour, self.start_minute)} hasta {fin}"


def validate_rule(weekday, start_hour: int, end_hour: int, start_minute: int = 0, end_minute: int = 0) -> str | None:
    """Mensaje de error, o None si la regla es válida."""
    if not (0 <= start_hour <= 23 and 1 <= end_hour <= 24):
        return "Las horas deben estar entre 00:00 y el fin del día."
    if start_minute % STEP_MIN or end_minute % STEP_MIN or not (0 <= start_minute < 60 and 0 <= end_minute < 60):
        return "Los minutos deben ser 00, 15, 30 o 45."
    if end_hour == 24 and end_minute:
        return "Después del fin del día no hay más horas."
    if start_hour * 60 + start_minute >= end_hour * 60 + end_minute:
        return "La hora de inicio debe ser menor que la de fin."
    if weekday is not None and not (0 <= weekday <= 6):
        return "El día no es válido."
    if weekday is None and start_hour == 0 and start_minute == 0 and end_hour == 24:
        return "Esa regla bloquearía todos los horarios de todos los días. Elige un día o una franja."
    return None
