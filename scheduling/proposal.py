"""Propuesta de tres horarios ordenados con el motivo de cada uno (HU-06).

Lógica pura, sin base de datos: recibe la disponibilidad de las dos partes y devuelve un
`Proposal` del contrato (contracts.py). Usa el módulo de coincidencia de TR-11 (matching.py)
para ponderar los bloques de una hora y sobre eso resuelve la duración, descarta lo que ya
pasó, evita opciones que se pisen y redacta el motivo de cada opción.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo

from .contracts import Proposal, ProposedSlot
from .matching import END_HOUR, HIGH_PREF, HOURS, Member, block_key, compute_block_scores
from .rules import RuleSpec

MAX_OPTIONS = 3


@dataclass(frozen=True)
class _Candidate:
    day: int
    hour: int  # hora de inicio
    blocks: int  # cuantos bloques de una hora ocupa
    start: datetime
    end: datetime
    pref: int  # suma de preferencias altas de ambas partes en sus bloques

    def overlaps(self, other: "_Candidate") -> bool:
        return self.start < other.end and other.start < self.end


def _members(executive_blocks: dict[str, int], counterpart_blocks: dict[str, int]) -> list[Member]:
    return [
        Member(id="ejecutivo", name="Ejecutivo", submitted=True, availability=dict(executive_blocks)),
        Member(id="contraparte", name="Contraparte", submitted=True, availability=dict(counterpart_blocks)),
    ]


def _candidates(
    *, executive_blocks, counterpart_blocks, duration_min, week_start: date, tz: tzinfo, now: datetime,
    rules: Sequence[RuleSpec] = (),
) -> list[_Candidate]:
    needed = max(1, math.ceil(duration_min / 60))
    scores = {s.key: s for s in compute_block_scores(_members(executive_blocks, counterpart_blocks))}
    out: list[_Candidate] = []
    for day in range(7):
        for hour in HOURS:
            if hour + needed > END_HOUR:
                break
            keys = [block_key(day, hour + i) for i in range(needed)]
            if not all(k in scores and scores[k].is_full_match for k in keys):
                continue
            start = datetime(*(week_start + timedelta(days=day)).timetuple()[:3], hour, tzinfo=tz)
            if start <= now:
                continue  # no se propone algo que ya pasó
            end = start + timedelta(minutes=duration_min)
            if any(rule.blocks(start, end) for rule in rules):
                continue  # viola una regla protegida del ejecutivo
            out.append(
                _Candidate(
                    day=day, hour=hour, blocks=needed, start=start,
                    end=end,
                    pref=sum(scores[k].high_pref_count for k in keys),
                )
            )
    return out


def _choose(candidates: list[_Candidate]) -> list[_Candidate]:
    """Hasta tres opciones: primero la mejor de cada día distinto, luego se completa sin pisar las ya elegidas."""
    ordered = sorted(candidates, key=lambda c: (-c.pref, c.start))
    chosen: list[_Candidate] = []
    for c in ordered:
        if len(chosen) == MAX_OPTIONS:
            break
        if all(c.day != x.day for x in chosen):
            chosen.append(c)
    for c in ordered:
        if len(chosen) == MAX_OPTIONS:
            break
        if c not in chosen and not any(c.overlaps(x) for x in chosen):
            chosen.append(c)
    return sorted(chosen, key=lambda c: (-c.pref, c.start))


def _states(blocks: dict[str, int], c: _Candidate) -> list[int]:
    return [blocks.get(block_key(c.day, c.hour + i), 0) for i in range(c.blocks)]


def explain(
    c: _Candidate, executive_blocks, counterpart_blocks, executive_name: str, counterpart_name: str,
    rules: Sequence[RuleSpec] = (),
) -> str:
    """Motivo, a partir de lo que cada parte marcó y de las reglas del ejecutivo que aplican ese día."""
    reason = _availability_reason(c, executive_blocks, counterpart_blocks, executive_name, counterpart_name)
    respected = [rule.label for rule in rules if rule.applies_on(c.start)]
    if respected:
        reason += " Respeta: " + "; ".join(respected) + "."
    return reason


def _availability_reason(c: _Candidate, executive_blocks, counterpart_blocks, executive_name, counterpart_name) -> str:
    exec_states, cp_states = _states(executive_blocks, c), _states(counterpart_blocks, c)
    exec_all, cp_all = all(s == HIGH_PREF for s in exec_states), all(s == HIGH_PREF for s in cp_states)
    exec_some, cp_some = any(s == HIGH_PREF for s in exec_states), any(s == HIGH_PREF for s in cp_states)
    if exec_all and cp_all:
        return f"{executive_name} y {counterpart_name} lo marcaron como preferido."
    if exec_all:
        return f"{executive_name} lo marcó como preferido y {counterpart_name} también puede."
    if cp_all:
        return f"{counterpart_name} lo marcó como preferido y {executive_name} también puede."
    if exec_some and cp_some:
        return "Ambos pueden. Incluye horas que cada uno prefiere."
    if exec_some:
        return f"Ambos pueden. Incluye horas que {executive_name} prefiere."
    if cp_some:
        return f"Ambos pueden. Incluye horas que {counterpart_name} prefiere."
    return f"{executive_name} y {counterpart_name} están disponibles."


def build_proposal(
    *,
    request_id,
    title: str,
    executive_name: str,
    counterpart_name: str,
    duration_min: int,
    week_start: date,
    executive_blocks: dict[str, int],
    counterpart_blocks: dict[str, int],
    now: datetime,
    tz: tzinfo,
    rules: Sequence[RuleSpec] = (),
) -> Proposal:
    """Devuelve la propuesta con hasta tres opciones ordenadas. Sin coincidencia, `slots` queda vacío."""
    candidates = _candidates(
        executive_blocks=executive_blocks, counterpart_blocks=counterpart_blocks,
        duration_min=duration_min, week_start=week_start, tz=tz, now=now, rules=rules,
    )
    slots = [
        ProposedSlot(
            id=f"{c.day}-{c.hour}", start=c.start, end=c.end, rank=rank,
            reason=explain(c, executive_blocks, counterpart_blocks, executive_name, counterpart_name, rules),
        )
        for rank, c in enumerate(_choose(candidates), start=1)
    ]
    return Proposal(
        request_id=str(request_id), title=title, counterpart_name=counterpart_name,
        duration_min=duration_min, slots=slots,
    )
