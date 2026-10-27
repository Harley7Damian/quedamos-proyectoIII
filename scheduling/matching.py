"""Lógica pura de coincidencia de horarios para "Quedamos" (TR-11).

Puerto directo de docs/referencia/matching.ts. Sin dependencias de Django ni
de la base de datos: son solo estructuras de datos y funciones puras, para
poder probarlas de forma aislada. Mayerly conecta esto después con
MeetingRequest para construir la Proposal de contracts.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field

DAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
DAYS_SHORT = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

START_HOUR = 8
END_HOUR = 22
HOURS = list(range(START_HOUR, END_HOUR))  # bloques: 8:00-9:00 ... 21:00-22:00

# Estados de disponibilidad de una celda.
UNAVAILABLE = 0
AVAILABLE = 1
HIGH_PREF = 2


@dataclass
class Member:
    id: str
    name: str
    submitted: bool
    availability: dict[str, int] = field(default_factory=dict)
    is_demo: bool = False  # integrante de ejemplo precargado en modo demo, no una persona real


@dataclass
class Group:
    code: str
    name: str
    created_at: float
    members: list[Member]


def block_key(day: int, hour: int) -> str:
    return f"{day}-{hour}"


def format_hour(hour: int) -> str:
    return f"{hour:02d}:00"


def format_block_label(day: int, hour: int) -> str:
    return f"{DAYS[day]} · {format_hour(hour)} - {format_hour(hour + 1)}"


@dataclass(frozen=True)
class BlockScore:
    day: int
    hour: int
    key: str
    available_count: int  # integrantes en "disponible" o "preferencia alta"
    high_pref_count: int  # integrantes específicamente en "preferencia alta"
    is_full_match: bool  # True si coincide el 100% de quienes respondieron


def compute_block_scores(members: list[Member]) -> list[BlockScore]:
    """Pondera cada bloque horario de la semana.

    Por cada bloque se cuenta cuántos integrantes lo marcaron disponible o
    con preferencia alta (ambos cuentan como disponibilidad), y por separado
    cuántos lo marcaron específicamente con preferencia alta. Los bloques sin
    ninguna disponibilidad se omiten.

    Orden: primero por cantidad de integrantes disponibles (desc.), y como
    desempate, por cantidad de integrantes con preferencia alta (desc.).
    """
    responders = [m for m in members if m.submitted]
    total = len(responders)

    scores: list[BlockScore] = []

    for day in range(len(DAYS)):
        for hour in HOURS:
            key = block_key(day, hour)
            available_count = 0
            high_pref_count = 0

            for member in responders:
                state = member.availability.get(key, UNAVAILABLE)
                if state >= AVAILABLE:
                    available_count += 1
                if state == HIGH_PREF:
                    high_pref_count += 1

            if available_count == 0:
                continue

            scores.append(
                BlockScore(
                    day=day,
                    hour=hour,
                    key=key,
                    available_count=available_count,
                    high_pref_count=high_pref_count,
                    is_full_match=total > 0 and available_count == total,
                )
            )

    scores.sort(key=lambda s: (s.available_count, s.high_pref_count), reverse=True)
    return scores


@dataclass(frozen=True)
class Suggestions:
    top: list[BlockScore]  # mejores bloques, ya ordenados y limitados
    full_matches: list[BlockScore]  # bloques donde coincide el 100%
    has_full_match: bool
    responded_count: int  # integrantes que ya marcaron su disponibilidad
    total_count: int  # integrantes totales del grupo, hayan o no respondido


def get_suggestions(members: list[Member], limit: int = 5) -> Suggestions:
    scores = compute_block_scores(members)
    full_matches = [s for s in scores if s.is_full_match]
    responded_count = sum(1 for m in members if m.submitted)

    return Suggestions(
        top=scores[:limit],
        full_matches=full_matches,
        has_full_match=len(full_matches) > 0,
        responded_count=responded_count,
        total_count=len(members),
    )