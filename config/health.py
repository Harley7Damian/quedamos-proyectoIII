"""Ruta de salud del servicio (TR-35): informa si la aplicación y la base de datos responden."""
import logging

from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

logger = logging.getLogger(__name__)


@require_safe
@never_cache
def health(request):
    """Responde 200 si la base de datos contesta y 503 si no. Es pública y no expone datos de usuarios ni detalles del error."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError as exc:
        logger.error("Verificacion de salud fallida: la base de datos no responde (%s)", type(exc).__name__)
        return JsonResponse(
            {"estado": "error", "aplicacion": "ok", "base_de_datos": "error"},
            status=503,
        )
    return JsonResponse({"estado": "ok", "aplicacion": "ok", "base_de_datos": "ok"})
