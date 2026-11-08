"""Metricas de uso (HU-10): tiempo hasta confirmar, rondas de propuesta y mensajes evitados.

Que se mide de verdad y que es una estimacion:

1. Tiempo hasta confirmar: medido. Es la diferencia entre la fecha de creacion de la solicitud y la fecha en que
   el ejecutivo aprobo una opcion.
2. Rondas de propuesta: medido. Cuantas veces se genero una propuesta con al menos una opcion.
3. Enlaces generados: medido. Cada enlace que la asistente genera para la contraparte o para el ejecutivo es un
   mensaje que tiene que enviar fuera del sistema.
4. Mensajes evitados: ESTIMADO. Resta de un valor de referencia los enlaces generados. El valor de referencia es
   un supuesto del equipo, no un dato medido ni una cifra de una fuente.

No se guarda nada del calendario de nadie: solo fechas de la propia solicitud y dos contadores.
"""
from dataclasses import dataclass
from datetime import timedelta
from statistics import mean, median

# Supuesto del equipo, sin fuente: coordinar una reunion externa por correo requiere al menos 6 mensajes
# (una propuesta, una respuesta y una confirmacion por cada una de las dos asistentes). Se contrasta con las
# pruebas con el profesor (TR-17) y con una entrevista a una asistente (HU-16); mientras tanto no es evidencia.
BASELINE_MESSAGES = 6


@dataclass(frozen=True)
class MeetingMetric:
    request: object
    time_to_confirm: timedelta
    rounds: int
    links_shared: int
    avoided: int


def meeting_metric(meeting_request) -> MeetingMetric:
    """Metrica de una reunion aprobada. El resultado de mensajes evitados nunca es negativo."""
    if not meeting_request.is_approved or meeting_request.decided_at is None:
        raise ValueError("Solo una reunion aprobada tiene metricas.")
    return MeetingMetric(
        request=meeting_request,
        time_to_confirm=max(meeting_request.decided_at - meeting_request.created_at, timedelta(0)),
        rounds=meeting_request.proposal_rounds,
        links_shared=meeting_request.links_shared,
        avoided=max(BASELINE_MESSAGES - meeting_request.links_shared, 0),
    )


def summarize(metrics) -> dict:
    """Resumen de varias reuniones. Sin reuniones confirmadas no hay promedios que mostrar."""
    metrics = list(metrics)
    if not metrics:
        return {"count": 0}
    times = [m.time_to_confirm for m in metrics]
    return {
        "count": len(metrics),
        "mean_time": sum(times, timedelta(0)) / len(times),
        "median_time": median(times),
        "mean_rounds": round(mean(m.rounds for m in metrics), 1),
        "avoided_total": sum(m.avoided for m in metrics),
        "avoided_mean": round(mean(m.avoided for m in metrics), 1),
    }
