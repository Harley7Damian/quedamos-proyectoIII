"""Acuerdos de la reunion (HU-18): de las notas pegadas a resumen, tareas y propuesta de seguimiento.

Aqui vive lo que sabe de Quedamos: el esquema que se le exige al modelo, la instruccion, los formularios de la vista
previa editable y el paso de lo que entendio el modelo a valores iniciales. Nada se guarda desde este modulo.
"""
from __future__ import annotations

from datetime import date

from django import forms

from meetings.models import MeetingRequest

from .esquemas import Entero, Lista, Objeto, Texto

MAX_NOTAS = 6000
MAX_TAREAS = 15
FILAS_EXTRA = 2  # filas vacias al final de la vista previa para agregar tareas que la IA no vio
MAX_RESUMEN = 1500

ESQUEMA = Objeto(
    {
        "resumen": Texto(MAX_RESUMEN),
        "tareas": Lista(
            Objeto(
                {
                    "descripcion": Texto(200),
                    "responsable": Texto(80, nullable=True),
                    "fecha_limite": Texto(10, nullable=True),
                }
            ),
            max_items=MAX_TAREAS,
        ),
        "seguimiento": Objeto({"asunto": Texto(120), "duracion_min": Entero(1, 600, nullable=True)}, nullable=True),
    }
)

_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def instruccion(hoy: date) -> str:
    """La fecha de hoy va en la instruccion para que el modelo convierta "el viernes" en una fecha concreta."""
    return "\n\n".join(
        [
            "Lees las notas o la transcripción de una reunión de trabajo y las conviertes en acuerdos. "
            "Devuelve un objeto JSON con tres claves. Escribe todo en español.",
            f"Hoy es {_DIAS[hoy.weekday()]} {hoy.isoformat()}.",
            '"resumen": un resumen de 3 a 6 oraciones con lo que se habló y se decidió, de máximo 1200 caracteres.',
            '"tareas": lista de máximo 15 tareas que las notas dejan comprometidas. Cada una es un objeto con '
            '"descripcion" (acción concreta, máximo 200 caracteres), "responsable" (la persona tal como aparece '
            'en las notas, o null si no se dice) y "fecha_limite" (fecha en formato AAAA-MM-DD calculada desde la '
            "fecha de hoy, o null si las notas no dan un plazo). No inventes tareas, responsables ni fechas.",
            '"seguimiento": si las notas piden otra reunión, un objeto con "asunto" (máximo 120 caracteres) y '
            '"duracion_min" (minutos, entero, o null si no se dice). Si no piden otra reunión, null.',
            'Ejemplo: "Revisamos el contrato. Luis envía la versión final el viernes. Ana confirma el presupuesto. '
            'Nos vemos de nuevo en dos semanas" con hoy lunes 2026-11-16 devuelve '
            '{"resumen": "Se revisó el contrato y se acordó cerrar la versión final y confirmar el presupuesto.", '
            '"tareas": [{"descripcion": "Enviar la versión final del contrato", "responsable": "Luis", '
            '"fecha_limite": "2026-11-20"}, {"descripcion": "Confirmar el presupuesto", "responsable": "Ana", '
            '"fecha_limite": null}], "seguimiento": {"asunto": "Seguimiento del contrato", "duracion_min": null}}.',
        ]
    )


def _fecha(texto):
    try:
        return date.fromisoformat(texto) if texto else None
    except ValueError:
        return None  # el modelo escribio algo que no es una fecha: se deja vacia y la persona la completa


def iniciales_tareas(datos: dict) -> list[dict]:
    return [
        {
            "descripcion": t["descripcion"],
            "responsable": t["responsable"] or "",
            "fecha_limite": _fecha(t["fecha_limite"]),
        }
        for t in datos["tareas"]
    ]


def iniciales_acuerdos(datos: dict) -> dict:
    seguimiento = datos.get("seguimiento")
    iniciales = {"resumen": datos["resumen"], "seguimiento_incluir": bool(seguimiento)}
    if seguimiento:
        iniciales["seguimiento_asunto"] = seguimiento["asunto"]
        if seguimiento["duracion_min"]:
            permitidas = [m for m, _ in MeetingRequest.DURATIONS]
            iniciales["seguimiento_duracion"] = min(
                permitidas, key=lambda m: (abs(m - seguimiento["duracion_min"]), m)
            )
    return iniciales


class AcuerdosForm(forms.Form):
    resumen = forms.CharField(
        label="Resumen", max_length=MAX_RESUMEN, widget=forms.Textarea(attrs={"rows": 5}), strip=True
    )
    seguimiento_incluir = forms.BooleanField(label="Proponer una reunión de seguimiento", required=False)
    seguimiento_asunto = forms.CharField(label="Asunto del seguimiento", max_length=120, required=False)
    seguimiento_duracion = forms.TypedChoiceField(
        label="Duración",
        choices=MeetingRequest.DURATIONS,
        coerce=int,
        required=False,
        empty_value=None,
        initial=30,
    )

    def clean(self):
        datos = super().clean()
        if datos.get("seguimiento_incluir"):
            if not datos.get("seguimiento_asunto"):
                self.add_error("seguimiento_asunto", "Escribe el asunto del seguimiento.")
            if not datos.get("seguimiento_duracion"):
                datos["seguimiento_duracion"] = 30
        return datos


class TareaForm(forms.Form):
    descripcion = forms.CharField(label="Tarea", max_length=200, required=False)
    responsable = forms.CharField(label="Responsable", max_length=80, required=False)
    fecha_limite = forms.DateField(
        label="Fecha límite", required=False, widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )

    @property
    def vacia(self) -> bool:
        """Una fila sin nada escrito no es una tarea: son las filas extra que la persona no uso."""
        campos = ("descripcion", "responsable", "fecha_limite")
        return not any(str(self[campo].value() or "").strip() for campo in campos)

    def clean(self):
        datos = super().clean()
        if not self.errors and not datos.get("descripcion") and (datos.get("responsable") or datos.get("fecha_limite")):
            self.add_error("descripcion", "Escribe qué hay que hacer o quita la marca de esta fila.")
        return datos
