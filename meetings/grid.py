"""Cuadricula semanal de disponibilidad: construir lo que se muestra y leer lo que se envia."""
import re
from datetime import date, timedelta

from scheduling.matching import AVAILABLE, DAYS_SHORT, HIGH_PREF, HOURS, block_key, format_hour

_FIELD = re.compile(r"b-([0-6])-(\d{1,2})")


def week_header(week_start: date):
    return [{"short": DAYS_SHORT[i], "date": week_start + timedelta(days=i)} for i in range(7)]


def grid_rows(blocks: dict[str, int]):
    return [
        {
            "label": format_hour(hour),
            "cells": [
                {"name": f"b-{day}-{hour}", "state": blocks.get(block_key(day, hour), 0)}
                for day in range(7)
            ],
        }
        for hour in HOURS
    ]


def parse_blocks(data) -> dict[str, int]:
    """Lee los campos b-<dia>-<hora> del formulario. Ignora todo lo que no sea valido."""
    blocks: dict[str, int] = {}
    for name in data:
        match = _FIELD.fullmatch(name)
        if not match:
            continue
        day, hour = int(match.group(1)), int(match.group(2))
        if hour not in HOURS:
            continue
        try:
            state = int(data.get(name))
        except (TypeError, ValueError):
            continue
        if state in (AVAILABLE, HIGH_PREF):
            blocks[block_key(day, hour)] = state
    return blocks
