"""Llamadas telefónicas reales vía Twilio (TR-85): escalamiento cuando el
usuario no confirmó el recordatorio de 5 minutos con /visto."""
import logging
from urllib.parse import quote

from django.conf import settings
from twilio.rest import Client

logger = logging.getLogger(__name__)


def hacer_llamada_recordatorio(telefono, texto):
    """Llama al número indicado y lee el texto del recordatorio en voz.
    Devuelve True si Twilio aceptó la llamada, False si algo falló."""
    if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_FROM_NUMBER):
        logger.warning("Twilio no está configurado; no se pudo llamar a %s.", telefono)
        return False
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        url = f"{settings.SITE_URL}/telegram/llamada-twiml/?texto={quote(texto)}"
        client.calls.create(to=telefono, from_=settings.TWILIO_FROM_NUMBER, url=url, method="GET")
        return True
    except Exception as exc:
        logger.warning("No se pudo llamar a %s: %s", telefono, type(exc).__name__)
        return False
