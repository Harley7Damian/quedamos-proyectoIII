"""Vistas de IA: captura inteligente (HU-17) y acuerdos de la reunion (HU-18).

La IA propone; solo se guarda lo que la persona confirma en la vista previa."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from meetings.forms import MeetingRequestForm, SchedulingRuleForm
from meetings.models import MeetingRequest

from . import acuerdos
from .captura import ESQUEMA, INSTRUCCION, MAX_REGLAS, ejecutivos_de, iniciales_reglas, iniciales_solicitud
from .gemini import IaError, pedir_json
from .models import AcuerdosReunion, TareaReunion


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


# ---------------------------------------------------------------- HU-18: acuerdos de la reunion


def _reunion_de_la_asistente(user, pk):
    """404 si no es visible (no se revela que existe); 403 si la ve pero no es asistente, que es quien los registra."""
    reunion = get_object_or_404(MeetingRequest.objects.visible_to(user).select_related("executive"), pk=pk)
    if not user.is_assistant:
        raise PermissionDenied("Esta acción corresponde a la asistente.")
    return reunion


def _motivo_para_no_registrar(reunion):
    if reunion.status != MeetingRequest.Status.APROBADA:
        return "Solo las reuniones aprobadas tienen acuerdos."
    if AcuerdosReunion.objects.filter(request=reunion).exists():
        return "Esta reunión ya tiene sus acuerdos guardados."
    return None


def _vista_acuerdos(request, reunion, notas, formulario, filas, total):
    contexto = {"r": reunion, "notas": notas, "form": formulario, "filas": filas, "total": total}
    return render(request, "ia/_vista_acuerdos.html", contexto)


@login_required
@require_POST
def acuerdos_generar(request, pk):
    user = request.user
    reunion = _reunion_de_la_asistente(user, pk)
    motivo = _motivo_para_no_registrar(reunion)
    if motivo:
        return _mensaje(request, motivo, "error")
    notas = request.POST.get("notas", "").strip()
    try:
        datos = pedir_json(
            user, acuerdos.instruccion(timezone.localdate()), notas, acuerdos.ESQUEMA, max_chars=acuerdos.MAX_NOTAS
        )
    except IaError as error:
        return _mensaje(request, error.mensaje_usuario, "error")

    iniciales = acuerdos.iniciales_tareas(datos) + [{}] * acuerdos.FILAS_EXTRA
    filas = [
        {"i": i, "incluir": True, "form": acuerdos.TareaForm(prefix=f"t{i}", initial=inicial)}
        for i, inicial in enumerate(iniciales)
    ]
    formulario = acuerdos.AcuerdosForm(initial=acuerdos.iniciales_acuerdos(datos))
    return _vista_acuerdos(request, reunion, notas, formulario, filas, len(filas))


@login_required
@require_POST
def acuerdos_confirmar(request, pk):
    user = request.user
    reunion = _reunion_de_la_asistente(user, pk)
    motivo = _motivo_para_no_registrar(reunion)
    if motivo:
        return _mensaje(request, motivo, "error")
    notas = request.POST.get("notas", "").strip()
    try:
        total = int(request.POST.get("total", "0"))
    except ValueError:
        total = 0
    if not notas or len(notas) > acuerdos.MAX_NOTAS or not 1 <= total <= acuerdos.MAX_TAREAS + acuerdos.FILAS_EXTRA:
        return _mensaje(request, "No se recibieron los acuerdos. Genera la vista previa otra vez.", "error")

    formulario = acuerdos.AcuerdosForm(request.POST)
    filas = []
    for i in range(total):
        if request.POST.get(f"t{i}-incluir"):
            filas.append({"i": i, "incluir": True, "form": acuerdos.TareaForm(request.POST, prefix=f"t{i}")})
    # Se evaluan todas para mostrar todos los errores juntos.
    validas = [formulario.is_valid()] + [fila["form"].is_valid() for fila in filas]
    if not all(validas):
        return _vista_acuerdos(request, reunion, notas, formulario, filas, total)

    datos = formulario.cleaned_data
    seguimiento = datos["seguimiento_incluir"]
    try:
        with transaction.atomic():
            guardados = AcuerdosReunion.objects.create(
                request=reunion,
                notas=notas,
                resumen=datos["resumen"],
                seguimiento_asunto=datos["seguimiento_asunto"] if seguimiento else "",
                seguimiento_duracion=datos["seguimiento_duracion"] if seguimiento else None,
                created_by=user,
            )
            tareas = [fila["form"].cleaned_data for fila in filas if not fila["form"].vacia]
            TareaReunion.objects.bulk_create(
                TareaReunion(
                    acuerdos=guardados,
                    descripcion=t["descripcion"],
                    responsable=t["responsable"],
                    fecha_limite=t["fecha_limite"],
                    orden=orden,
                )
                for orden, t in enumerate(tareas)
            )
    except IntegrityError:  # dos confirmaciones a la vez: gana la primera
        return _mensaje(request, "Esta reunión ya tiene sus acuerdos guardados.", "error")
    messages.success(request, "Acuerdos guardados.")
    respuesta = HttpResponse()
    respuesta["HX-Redirect"] = reverse("request_detail", args=[reunion.pk])
    return respuesta


@login_required
def seguimiento(request, pk):
    """Abre el formulario de solicitud ya precargado con el seguimiento propuesto. No crea nada: la persona lo envia."""
    user = request.user
    reunion = _reunion_de_la_asistente(user, pk)
    guardados = AcuerdosReunion.objects.filter(request=reunion).first()
    if guardados is None or not guardados.tiene_seguimiento:
        raise Http404("Esta reunión no tiene un seguimiento propuesto.")
    iniciales = {
        "executive": reunion.executive_id,
        "title": guardados.seguimiento_asunto,
        "counterpart_name": reunion.counterpart_name,
        "counterpart_email": reunion.counterpart_email,
    }
    if guardados.seguimiento_duracion:
        iniciales["duration_min"] = guardados.seguimiento_duracion
    formulario = MeetingRequestForm(initial=iniciales, user=user, executives=ejecutivos_de(user))
    formulario.fields["week"].widget.format = "%Y-%m-%d"
    return render(request, "ia/seguimiento.html", {"form": formulario, "r": reunion, "me": user})
