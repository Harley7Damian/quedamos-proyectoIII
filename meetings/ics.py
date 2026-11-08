"""Archivo de invitacion (.ics) de una reunion aprobada (HU-09), segun la RFC 5545.

El archivo solo lleva lo que la propia reunion ya muestra a las partes: asunto, nombres, fecha y hora.
Nunca incluye las notas internas de la asistente ni la disponibilidad de nadie. El UID y la marca de
creacion (DTSTAMP) son estables, de modo que descargar dos veces el mismo archivo no duplica el evento
en el calendario.
"""
from datetime import timezone as dt_timezone

PRODID = "-//Quedamos//Coordinacion de reuniones//ES"
FOLD_LIMIT = 75  # octetos por linea, incluido el espacio inicial de las lineas de continuacion


def escape_text(value: str) -> str:
    """Escapa un valor de texto: barra invertida, punto y coma, coma y saltos de linea."""
    value = value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    return value.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")


def fold_line(line: str) -> str:
    """Divide una linea larga a 75 octetos sin partir un caracter de varios bytes."""
    parts, current, size = [], "", 0
    for char in line:
        width = len(char.encode("utf-8"))
        if size + width > FOLD_LIMIT:
            parts.append(current)
            current, size = " " + char, 1 + width
        else:
            current += char
            size += width
    parts.append(current)
    return "\r\n".join(parts)


def _utc(value) -> str:
    return value.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_ics(meeting_request) -> str:
    """Devuelve el contenido .ics de una reunion aprobada. Falla si aun no hay una opcion aprobada."""
    if not meeting_request.is_approved:
        raise ValueError("Solo una reunion aprobada genera invitacion.")
    summary = f"{meeting_request.title} con {meeting_request.counterpart_name}"
    description = (
        f"Reunión coordinada con Quedamos. Ejecutivo: {meeting_request.executive.full_name}. "
        f"Contraparte: {meeting_request.counterpart_name}."
    )
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:quedamos-{meeting_request.pk}@quedamos",
        f"DTSTAMP:{_utc(meeting_request.decided_at or meeting_request.approved_start)}",
        f"DTSTART:{_utc(meeting_request.approved_start)}",
        f"DTEND:{_utc(meeting_request.approved_end)}",
        f"SUMMARY:{escape_text(summary)}",
        f"DESCRIPTION:{escape_text(description)}",
        "STATUS:CONFIRMED",
        "SEQUENCE:0",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(fold_line(line) for line in lines) + "\r\n"
