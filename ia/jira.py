"""Envio de tareas a Jira Cloud por su API REST (HU-20).

Una sola puerta para hablar con Jira: autenticacion por correo y token (basic), creacion de una incidencia de tipo
Tarea y traduccion de los fallos a mensajes claros. Usa solo la biblioteca estandar (https a un host fijo). El token
viaja en una cabecera, nunca en la URL, y no se escribe en registros, mensajes ni respuestas.
"""
from __future__ import annotations

import base64
import http.client
import json
import logging
import re

from django.conf import settings

logger = logging.getLogger("ia")

ETIQUETA = "quedamos-ia"
_HOST = re.compile(r"[A-Za-z0-9][A-Za-z0-9.\-]{1,100}")
_CLAVE = re.compile(r"[A-Z][A-Z0-9_]{1,19}-[0-9]{1,9}")
_SUGERENCIA = "Puedes usar la exportación CSV mientras tanto."


class JiraError(Exception):
    """Fallo al hablar con Jira. `mensaje_usuario` es seguro de mostrar: nunca incluye el token ni texto de Jira."""

    mensaje_usuario = f"No se pudo enviar la tarea a Jira. {_SUGERENCIA}"

    def __init__(self, mensaje_usuario: str | None = None):
        super().__init__(mensaje_usuario or self.mensaje_usuario)
        if mensaje_usuario:
            self.mensaje_usuario = mensaje_usuario


class JiraNoConfigurado(JiraError):
    mensaje_usuario = f"Jira no está configurado en esta instalación. {_SUGERENCIA}"


_MENSAJES_POR_ESTADO = {
    401: "Jira rechazó las credenciales (el token es incorrecto o venció).",
    403: "La cuenta de Jira no tiene permiso para crear incidencias en el proyecto.",
    404: "No se encontró el proyecto de Jira configurado.",
    429: "Jira pidió esperar porque recibió demasiadas solicitudes. Inténtalo en unos minutos.",
}


def _host() -> str:
    return (settings.JIRA_SITE or "").strip().removeprefix("https://").rstrip("/")


def configurado() -> bool:
    """El boton "Enviar a Jira" solo se ofrece si estan las cuatro variables y el sitio parece un nombre de host."""
    datos = (settings.JIRA_SITE, settings.JIRA_EMAIL, settings.JIRA_TOKEN, settings.JIRA_PROJECT)
    return all((d or "").strip() for d in datos) and bool(_HOST.fullmatch(_host()))


def url_incidencia(clave: str) -> str:
    """Enlace a la incidencia para mostrarlo; vacio si no hay sitio configurado o la clave no tiene forma de clave."""
    return f"https://{_host()}/browse/{clave}" if configurado() and _CLAVE.fullmatch(clave or "") else ""


def _adf(parrafos) -> dict:
    """Descripcion en Atlassian Document Format, el unico formato que acepta la API v3."""
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": texto}]} for texto in parrafos],
    }


def armar_cuerpo(tarea, con_fecha: bool = True) -> dict:
    reunion = tarea.acuerdos.request
    parrafos = [f"Tarea acordada en la reunión «{reunion.title}» con {reunion.counterpart_name}."]
    if tarea.responsable:
        parrafos.append(f"Responsable: {tarea.responsable}.")
    if tarea.fecha_limite:
        parrafos.append(f"Fecha límite: {tarea.fecha_limite.strftime('%d/%m/%Y')}.")
    parrafos.append("Creada desde Quedamos.")
    campos = {
        "project": {"key": settings.JIRA_PROJECT.strip()},
        "issuetype": {"name": settings.JIRA_ISSUE_TYPE},
        "summary": tarea.descripcion[:255],
        "labels": [ETIQUETA],
        "description": _adf(parrafos),
    }
    if con_fecha and tarea.fecha_limite:
        campos["duedate"] = tarea.fecha_limite.isoformat()
    return {"fields": campos}


def _enviar(cuerpo: dict):
    """Unica funcion que sale a la red. Devuelve (estado HTTP, JSON de la respuesta). Las pruebas la reemplazan."""
    credenciales = f"{settings.JIRA_EMAIL.strip()}:{settings.JIRA_TOKEN.strip()}".encode()
    cabeceras = {
        "Authorization": "Basic " + base64.b64encode(credenciales).decode(),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    conexion = http.client.HTTPSConnection(_host(), timeout=settings.JIRA_TIMEOUT)
    try:
        conexion.request("POST", "/rest/api/3/issue", body=json.dumps(cuerpo).encode(), headers=cabeceras)
        respuesta = conexion.getresponse()
        crudo = respuesta.read(1_000_000)
        try:
            datos = json.loads(crudo.decode("utf-8")) if crudo else {}
        except ValueError:
            datos = {}
        return respuesta.status, datos if isinstance(datos, dict) else {}
    finally:
        conexion.close()


def _llamar(cuerpo: dict):
    try:
        return _enviar(cuerpo)
    except (OSError, http.client.HTTPException) as error:
        # Se registra solo el tipo de fallo: el texto de la excepcion podria traer datos de la conexion.
        logger.warning("Jira: sin respuesta (%s)", type(error).__name__)
        raise JiraError(f"No se pudo conectar con Jira. Inténtalo de nuevo. {_SUGERENCIA}") from None


def _rechaza_la_fecha(datos: dict) -> bool:
    """Algunos proyectos no tienen el campo de fecha en su pantalla de creacion: Jira responde 400 nombrandolo."""
    return "duedate" in (datos.get("errors") or {})


def crear_incidencia(tarea) -> str:
    """Crea la incidencia en el proyecto configurado y devuelve su clave. Lanza JiraError con un mensaje claro."""
    if not configurado():
        raise JiraNoConfigurado()
    estado, datos = _llamar(armar_cuerpo(tarea))
    if estado == 400 and tarea.fecha_limite and _rechaza_la_fecha(datos):
        estado, datos = _llamar(armar_cuerpo(tarea, con_fecha=False))  # la fecha ya va en la descripcion
    if estado == 201:
        clave = datos.get("key")
        if isinstance(clave, str) and _CLAVE.fullmatch(clave):
            return clave
        logger.error("Jira: respuesta 201 sin una clave valida")
        raise JiraError()
    logger.error("Jira: creacion rechazada con estado=%s", estado)
    if estado in _MENSAJES_POR_ESTADO:
        raise JiraError(f"{_MENSAJES_POR_ESTADO[estado]} {_SUGERENCIA}")
    if estado >= 500:
        raise JiraError(f"Jira no está disponible por ahora. {_SUGERENCIA}")
    raise JiraError(f"Jira no aceptó la tarea. Revisa la configuración del proyecto. {_SUGERENCIA}")
