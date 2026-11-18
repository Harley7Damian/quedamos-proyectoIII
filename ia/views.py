"""Captura inteligente (HU-17). La IA propone; solo se guarda lo que la persona confirma en la vista previa."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from meetings.forms import MeetingRequestForm, SchedulingRuleForm

from .captura import ESQUEMA, INSTRUCCION, MAX_REGLAS, ejecutivos_de, iniciales_reglas, iniciales_solicitud
from .gemini import IaError, pedir_json


def _mensaje(request, texto, nivel="info"):
    return render(request, "ia/_mensaje.html", {"texto": texto, "nivel": nivel})


def _vista_reglas(request, filas, ejecutivos, total, ejecutivo_id=None):
    contexto = {"filas": filas, "ejecutivos": ejecutivos, "total": total, "ejecutivo_id": ejecutivo_id}
    return render(request, "ia/_vista_reglas.html", contexto)


@login_required
@require_POST
def capturar(request):
    user = request.user
    ejecutivos = ejecutivos_de(user)
    if not ejecutivos.exists():
        return _mensaje(request, "Vincúlate con un ejecutivo para usar la captura inteligente.")
    try:
        datos = pedir_json(user, INSTRUCCION, request.POST.get("texto", ""), ESQUEMA)
    except IaError as error:
        return _mensaje(request, error.mensaje_usuario, "error")

    if datos["intencion"] == "solicitud":
        if user.is_executive:
            return _mensaje(
                request,
                "Las solicitudes de reunión las registra tu asistente. "
                "Desde aquí puedes dictar reglas de horario protegido.",
            )
        formulario = MeetingRequestForm(
            initial=iniciales_solicitud(datos, timezone.localdate()),
            user=user,
            executives=ejecutivos,
            auto_id="captura_%s",  # evita ids repetidos con el formulario manual del panel
        )
        formulario.fields["week"].widget.format = "%Y-%m-%d"  # el campo de fecha del navegador exige formato ISO
        return render(request, "ia/_vista_solicitud.html", {"form": formulario})

    if datos["intencion"] == "regla" and datos["reglas"]:
        filas = [
            {
                "i": i,
                "incluir": True,
                "form": SchedulingRuleForm(prefix=f"r{i}", initial=inicial, user=user, executives=ejecutivos),
            }
            for i, inicial in enumerate(iniciales_reglas(datos))
        ]
        return _vista_reglas(request, filas, ejecutivos, len(filas))

    return _mensaje(
        request,
        "No pude identificar una solicitud ni una regla. Prueba con algo como: "
        "\"reunión con el proveedor de una hora la próxima semana\" o \"nada antes de las 10\".",
    )


@login_required
@require_POST
def confirmar_reglas(request):
    user = request.user
    ejecutivos = ejecutivos_de(user)
    try:
        total = int(request.POST.get("total", "0"))
    except ValueError:
        total = 0
    if not 1 <= total <= MAX_REGLAS:
        return _mensaje(request, "No se recibieron reglas para guardar.", "error")

    ejecutivo_id = request.POST.get("executive", "")
    filas = []
    for i in range(total):
        if not request.POST.get(f"r{i}-incluir"):
            continue
        datos = request.POST.copy()
        datos[f"r{i}-executive"] = ejecutivo_id  # el ejecutivo es uno solo para todo el lote; el formulario lo valida
        formulario = SchedulingRuleForm(datos, prefix=f"r{i}", user=user, executives=ejecutivos)
        filas.append({"i": i, "incluir": True, "form": formulario})
    if not filas:
        return _mensaje(request, "Marca al menos una regla para guardarla.", "error")

    validas = [fila["form"].is_valid() for fila in filas]  # se evaluan todas para mostrar todos los errores juntos
    if not all(validas):
        return _vista_reglas(request, filas, ejecutivos, total, ejecutivo_id)

    with transaction.atomic():
        for fila in filas:
            fila["form"].save()
    messages.success(request, "Regla guardada." if len(filas) == 1 else f"{len(filas)} reglas guardadas.")
    respuesta = HttpResponse()
    respuesta["HX-Redirect"] = reverse("rules")
    return respuesta
