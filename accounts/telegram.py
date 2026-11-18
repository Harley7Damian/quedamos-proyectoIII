import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/{method}"


def _sanitize_for_log(value: object) -> str:
    """Neutraliza saltos de línea para evitar log injection."""
    return str(value).replace("\r", "").replace("\n", "")


def enviar_mensaje_telegram(chat_id: str, texto: str) -> bool:
    """Envía un mensaje por Telegram. Devuelve True si se envió, False si falló (y lo registra en el log)."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN no está configurado; no se puede enviar el mensaje.")
        return False
    url = TELEGRAM_API_URL.format(token=token, method="sendMessage")
    try:
        response = requests.post(url, json={"chat_id": chat_id, "text": texto}, timeout=10)
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        # No se registra 'exc' completo: el error de requests puede incluir la URL de la
        # llamada, que contiene el token del bot. Solo se guarda el tipo de error.
        logger.warning(
            "No se pudo enviar el mensaje de Telegram a %s (%s).",
            _sanitize_for_log(chat_id),
            type(exc).__name__,
        )
        return False
    