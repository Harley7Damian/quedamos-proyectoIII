"""Captura inteligente (HU-17): de una frase dictada o escrita a una solicitud o a reglas de horario protegido.

Aqui vive lo que sabe de Quedamos: el esquema que se le exige al modelo, la instruccion y el paso de lo que entendio
a valores iniciales de los formularios que ya existen. Nada se guarda desde este modulo.
"""
from __future__ import annotations

from datetime import date, timedelta

from accounts.models import User
from meetings.models import MeetingRequest
from meetings.weeks import monday_of

from .esquemas import Entero, Lista, Objeto, Opcion, Texto

MAX_REGLAS = 8

ESQUEMA = Objeto(
    {
        "intencion": Opcion(("solicitud", "regla", "otro")),
        "solicitud": Objeto(
            {
                "asunto": Texto(120, nullable=True),
                "contraparte": Texto(80, nullable=True),
                "duracion_min": Entero(1, 600, nullable=True),
                "semana": Opcion(("esta", "proxima"), nullable=True),
                "notas": Texto(500, nullable=True),
            },
            nullable=True,
        ),
        "reglas": Lista(
            Objeto({"dia": Entero(0, 6, nullable=True), "desde": Entero(0, 23), "hasta": Entero(1, 24)}),
            max_items=MAX_REGLAS,
            nullable=True,
        ),
    }
)

INSTRUCCION = "\n\n".join(
    [
        "Interpretas lo que una asistente ejecutiva dicta o escribe sobre reuniones. "
        "Devuelve un objeto JSON con tres claves.",
        '"intencion": "solicitud" si la persona pide coordinar o agendar una reunión; '
        '"regla" si describe horarios en los que el ejecutivo no debe tener reuniones; '
        '"otro" en cualquier otro caso.',
        '"solicitud": si la intención es solicitud, un objeto con "asunto" (motivo breve), '
        '"contraparte" (persona o empresa con quien será la reunión), "duracion_min" (minutos, entero), '
        '"semana" ("esta" o "proxima", sin tilde) y "notas" (detalle adicional). '
        "Todo dato que la persona no dijo va en null. Si la intención no es solicitud, null.",
        '"reglas": si la intención es regla, una lista de máximo 8 objetos con "dia" (0 lunes, 1 martes, '
        "2 miércoles, 3 jueves, 4 viernes, 5 sábado, 6 domingo; null si aplica todos los días), "
        '"desde" (hora de inicio, entero de 0 a 23) y "hasta" (hora de fin, entero de 1 a 24). '
        "Si la intención no es regla, null.",
        "Las horas van en formato de 24 horas. Interpreta las horas ambiguas como horario de oficina: "
        '"de 1 a 2" es 13 a 14. "Nada antes de las 10" es desde 0 hasta 10. '
        '"Nada después de las 6 de la tarde" es desde 18 hasta 24. Un día completo es desde 0 hasta 24.',
        'Ejemplo 1: "reunión con el proveedor de una hora la próxima semana para revisar el contrato" devuelve '
        '{"intencion": "solicitud", "solicitud": {"asunto": "Revisar el contrato", "contraparte": "Proveedor", '
        '"duracion_min": 60, "semana": "proxima", "notas": null}, "reglas": null}.',
        'Ejemplo 2: "nada antes de las 10 y el viernes protegido" devuelve '
        '{"intencion": "regla", "solicitud": null, "reglas": [{"dia": null, "desde": 0, "hasta": 10}, '
        '{"dia": 4, "desde": 0, "hasta": 24}]}.',
        'Ejemplo 3: "qué tiempo hará mañana" devuelve {"intencion": "otro", "solicitud": null, "reglas": null}.',
    ]
)


def ejecutivos_de(user):
    """Ejecutivos a los que la persona puede atender: ella misma (ejecutivo) o sus vinculos (asistente)."""
    if user.is_executive:
        return User.objects.filter(pk=user.pk)
    return User.objects.filter(assistant_links__assistant=user)


def _duracion_mas_cercana(minutos: int) -> int:
    permitidas = [m for m, _ in MeetingRequest.DURATIONS]
    return min(permitidas, key=lambda m: (abs(m - minutos), m))


def iniciales_solicitud(datos: dict, hoy: date) -> dict:
    """Valores iniciales del formulario de solicitud. Lo que la persona no dijo no se incluye (queda vacio)."""
    s = datos.get("solicitud") or {}
    iniciales = {}
    if s.get("asunto"):
        iniciales["title"] = s["asunto"]
    if s.get("contraparte"):
        iniciales["counterpart_name"] = s["contraparte"]
    if s.get("duracion_min"):
        iniciales["duration_min"] = _duracion_mas_cercana(s["duracion_min"])
    if s.get("notas"):
        iniciales["notes"] = s["notas"]
    if s.get("semana"):
        lunes = monday_of(hoy)
        iniciales["week"] = lunes if s["semana"] == "esta" else lunes + timedelta(days=7)
    return iniciales


def iniciales_reglas(datos: dict) -> list[dict]:
    return [
        {"weekday": r["dia"], "start_hour": r["desde"], "end_hour": r["hasta"]} for r in (datos.get("reglas") or [])
    ]
