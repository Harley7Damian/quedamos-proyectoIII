"""TR-57: recorrido por pasos de una solicitud (solo presentacion; no cambia el flujo ni los estados)."""
from types import SimpleNamespace

HECHO = "hecho"
ACTUAL = "actual"
PENDIENTE = "pendiente"

NOMBRES = [
    "Solicitud creada",
    "Enlace a la contraparte",
    "Disponibilidades",
    "Propuesta",
    "Aprobación",
    "Confirmada",
]


def pasos_de(solicitud, ejecutivo_respondio, contraparte_respondio):
    """Seis pasos con su estado (hecho, actual o pendiente) y una ayuda corta para el actual.

    El paso actual es el primero que aun no se cumplio; no hay mas de uno. Una solicitud cancelada no tiene recorrido.
    """
    if solicitud.status == "cancelada":
        return []
    aprobada = solicitud.status == "aprobada"
    hay_propuesta = solicitud.status in ("propuesta", "aprobada")
    cumplidos = [
        True,
        bool(contraparte_respondio) or aprobada or hay_propuesta,
        bool(ejecutivo_respondio and contraparte_respondio) or aprobada or hay_propuesta,
        hay_propuesta,
        aprobada,
        aprobada,
    ]
    if solicitud.new_options_requested_at and not aprobada:
        # El ejecutivo pidio otras opciones: se vuelve a la propuesta.
        cumplidos[3:] = [False, False, False]
    ayudas = {
        1: "Comparte el enlace para que la contraparte marque su disponibilidad.",
        2: "Falta la disponibilidad del ejecutivo.",
        3: "Genera la propuesta de tres horarios.",
        4: "El ejecutivo aprueba una opción con un toque.",
        5: "Descarga la invitación y avisa a la contraparte.",
    }
    if solicitud.new_options_requested_at and not aprobada:
        ayudas[3] = "Se pidieron otras opciones: falta una nueva propuesta."
    pasos = []
    actual_asignado = False
    for i, nombre in enumerate(NOMBRES):
        if cumplidos[i]:
            estado = HECHO
        elif not actual_asignado:
            estado, actual_asignado = ACTUAL, True
        else:
            estado = PENDIENTE
        pasos.append(
            SimpleNamespace(
                numero=i + 1, nombre=nombre, estado=estado, ayuda=ayudas.get(i, "") if estado == ACTUAL else ""
            )
        )
    return pasos
