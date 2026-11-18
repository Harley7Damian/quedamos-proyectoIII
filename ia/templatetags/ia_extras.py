from django import template
from django.conf import settings

from meetings.models import MeetingRequest

from ..acuerdos import MAX_NOTAS
from ..models import AcuerdosReunion

register = template.Library()


@register.simple_tag
def ia_activa() -> bool:
    """La captura inteligente solo se muestra si hay una clave de Gemini configurada."""
    return bool(settings.GEMINI_API_KEY)


@register.inclusion_tag("ia/_acuerdos.html", takes_context=True)
def acuerdos_reunion(context, reunion):
    """Seccion "Despues de la reunion" del detalle. Solo existe en solicitudes aprobadas y para quien ya las ve."""
    usuario = context["me"]
    guardados = (
        AcuerdosReunion.objects.filter(request=reunion).select_related("created_by").prefetch_related("tareas").first()
    )
    puede_generar = guardados is None and usuario.is_assistant and bool(settings.GEMINI_API_KEY)
    mostrar = reunion.status == MeetingRequest.Status.APROBADA and (guardados is not None or puede_generar)
    return {
        "mostrar": mostrar,
        "r": reunion,
        "me": usuario,
        "acuerdos": guardados,
        "tareas": list(guardados.tareas.all()) if guardados else [],
        "max_notas": MAX_NOTAS,
    }
