from datetime import datetime, timedelta, timezone

from .contracts import Proposal, ProposedSlot

LIMA = timezone(timedelta(hours=-5))


def _slot(sid: str, rank: int, day: int, hour: int, minute: int, minutes: int, reason: str) -> ProposedSlot:
    start = datetime(2026, 10, day, hour, minute, tzinfo=LIMA)
    return ProposedSlot(id=sid, rank=rank, start=start, end=start + timedelta(minutes=minutes), reason=reason)


MOCK_PROPOSAL = Proposal(
    request_id="demo-1",
    title="Revisión trimestral de ventas",
    counterpart_name="Pedro Gómez",
    duration_min=45,
    slots=[
        _slot("s1", 1, 27, 10, 0, 45, "Ambas agendas están libres y respeta la regla de no reunirse antes de las 10."),
        _slot("s2", 2, 28, 15, 0, 45, "Libre para ambos. Queda después del bloque de almuerzo."),
        _slot("s3", 3, 29, 11, 30, 45, "Libre para ambos, pero es el día con más reuniones de la semana."),
    ],
)
