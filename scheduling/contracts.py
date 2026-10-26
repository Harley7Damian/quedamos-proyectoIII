"""Contrato de datos del Modulo 2 (propuesta de horarios y aprobacion).

Rossy construye la pantalla contra estas estructuras y los datos de ejemplo de `mock.py`.
Mayerly conecta despues los mismos objetos con la base de datos. No cambiar nombres sin avisar.
"""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ProposedSlot:
    id: str
    start: datetime  # con zona horaria
    end: datetime
    reason: str  # por que se propone este horario, en una frase
    rank: int  # 1 es la mejor opcion


@dataclass(frozen=True)
class Proposal:
    request_id: str
    title: str
    counterpart_name: str
    duration_min: int
    slots: list[ProposedSlot]
