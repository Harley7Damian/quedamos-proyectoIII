"""Tablero de tareas de las reuniones y exportacion CSV para Jira (HU-19).

Las tareas las crea HU-18 al confirmar los acuerdos. Aqui solo se listan, se filtran, se marcan como hechas y se
exportan; quien ve una tarea es quien ya puede ver su solicitud (MeetingRequest.visible_to).
"""
import csv
import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.views.decorators.http import require_POST, require_safe

from meetings.models import MeetingRequest

from . import jira
from .models import TareaReunion

ETIQUETA_JIRA = "quedamos-ia"
TIPO_JIRA = "Tarea"
COLUMNAS_CSV = ("Resumen", "Descripción", "Tipo", "Fecha límite", "Etiquetas")
ESTADOS = {"pendiente": False, "hecha": True}
_INICIOS_DE_FORMULA = ("=", "+", "-", "@", "\t", "\r")


def tareas_visibles(user):
    reuniones = MeetingRequest.objects.visible_to(user)
    return TareaReunion.objects.filter(acuerdos__request__in=reuniones).select_related("acuerdos__request")


def _filtros(parametros):
    """Estado y reunion validos del querystring. Un valor que no se entiende se ignora, no da error."""
    estado = parametros.get("estado") if parametros.get("estado") in ESTADOS else ""
    reunion = parametros.get("reunion", "")
    return {"estado": estado, "reunion": reunion if reunion.isdigit() else ""}


def _filtrar(consulta, filtros):
    if filtros["estado"]:
        consulta = consulta.filter(hecha=ESTADOS[filtros["estado"]])
    if filtros["reunion"]:
        consulta = consulta.filter(acuerdos__request_id=int(filtros["reunion"]))
    return consulta.order_by("hecha", F("fecha_limite").asc(nulls_last=True), "acuerdos__request__title", "orden", "id")


def _con_filtros(nombre, filtros):
    consulta = urlencode({k: v for k, v in filtros.items() if v})
    return reverse(nombre) + (f"?{consulta}" if consulta else "")


@login_required
@require_safe
def tablero(request):
    user = request.user
    filtros = _filtros(request.GET)
    visibles = tareas_visibles(user)
    reuniones = (
        MeetingRequest.objects.visible_to(user).filter(acuerdos__isnull=False).order_by("-approved_start", "-id")
    )
    hoy = timezone.localdate()
    tareas = list(_filtrar(visibles, filtros))
    for tarea in tareas:
        tarea.vencida = bool(tarea.fecha_limite and tarea.fecha_limite < hoy and not tarea.hecha)
        tarea.url_jira = jira.url_incidencia(tarea.jira_key)
    contexto = {
        "me": user,
        "tareas": tareas,
        "filtros": filtros,
        "reuniones": reuniones,
        "total": visibles.count(),
        "pendientes": visibles.filter(hecha=False).count(),
        "url_csv": _con_filtros("ia_tareas_csv", filtros),
        "puede_enviar_a_jira": user.is_assistant and jira.configurado(),
    }
    return render(request, "ia/tareas.html", contexto)


@login_required
@require_POST
def cambiar_estado(request, pk):
    """Marca una tarea como hecha o la reabre. 404 si el usuario no ve la solicitud de la tarea."""
    tarea = get_object_or_404(tareas_visibles(request.user), pk=pk)
    tarea.hecha = not tarea.hecha
    tarea.save(update_fields=["hecha"])
    messages.success(request, "Tarea marcada como hecha." if tarea.hecha else "Tarea reabierta.")
    return redirect(_con_filtros("ia_tareas", _filtros(request.POST)))


@login_required
@require_POST
def enviar_a_jira(request, pk):
    """Crea la incidencia de una tarea en Jira, una sola vez. Si algo falla, la tarea no queda marcada como enviada."""
    user = request.user
    destino = redirect(_con_filtros("ia_tareas", _filtros(request.POST)))
    # 404 si no la ve (no se revela que existe); 403 si la ve pero no es asistente, que es quien envia.
    get_object_or_404(tareas_visibles(user), pk=pk)
    if not user.is_assistant:
        raise PermissionDenied("Esta acción corresponde a la asistente.")
    if not jira.configurado():
        messages.error(request, jira.JiraNoConfigurado.mensaje_usuario)
        return destino
    with transaction.atomic():
        # La fila queda bloqueada (en PostgreSQL) mientras se llama a Jira: un doble clic no crea dos incidencias.
        tarea = TareaReunion.objects.select_for_update().select_related("acuerdos__request").get(pk=pk)
        if tarea.enviada_a_jira:
            messages.info(request, f"Esta tarea ya está en Jira ({tarea.jira_key}).")
            return destino
        try:
            tarea.jira_key = jira.crear_incidencia(tarea)
        except jira.JiraError as error:
            messages.error(request, error.mensaje_usuario)
            return destino
        tarea.save(update_fields=["jira_key"])
    messages.success(request, f"Tarea enviada a Jira: {tarea.jira_key}.")
    return destino


def _celda(valor) -> str:
    """Neutraliza las celdas que Excel o Calc leerian como formula (inyeccion de formulas en CSV)."""
    texto = "" if valor is None else str(valor)
    return "'" + texto if texto.startswith(_INICIOS_DE_FORMULA) else texto


def _descripcion(tarea) -> str:
    reunion = tarea.acuerdos.request
    partes = [f"Tarea acordada en la reunión «{reunion.title}» con {reunion.counterpart_name}."]
    if tarea.responsable:
        partes.append(f"Responsable: {tarea.responsable}.")
    return " ".join(partes)


def fila_csv(tarea) -> list:
    return [
        _celda(tarea.descripcion),
        _celda(_descripcion(tarea)),
        TIPO_JIRA,
        tarea.fecha_limite.isoformat() if tarea.fecha_limite else "",
        ETIQUETA_JIRA,
    ]


@login_required
@require_safe
def exportar_csv(request):
    """CSV en UTF-8 con BOM (para que Excel respete tildes y eñes) que se mapea en el importador de CSV de Jira."""
    tareas = _filtrar(tareas_visibles(request.user), _filtros(request.GET))
    salida = io.StringIO()
    salida.write("﻿")
    escritor = csv.writer(salida, lineterminator="\r\n")
    escritor.writerow(COLUMNAS_CSV)
    for tarea in tareas:
        escritor.writerow(fila_csv(tarea))
    respuesta = HttpResponse(salida.getvalue(), content_type="text/csv; charset=utf-8")
    respuesta["Content-Disposition"] = 'attachment; filename="tareas_quedamos.csv"'
    return respuesta
