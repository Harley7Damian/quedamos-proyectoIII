"""Enlace firmado para la contraparte (HU-05).

El enlace no guarda nada en la base de datos: lleva el id de la solicitud firmado con la
SECRET_KEY y una marca de tiempo. Si se altera o vence, deja de funcionar. Solo da acceso
a esa solicitud. Para la aprobacion del ejecutivo (HU-08) se usara otra sal distinta.
"""
from django.conf import settings
from django.core import signing

SALT = "quedamos.contraparte.v1"


class InvalidLink(Exception):
    pass


class ExpiredLink(InvalidLink):
    pass


def make_token(request_id: int) -> str:
    return signing.dumps({"r": int(request_id)}, salt=SALT)


def read_token(token: str) -> int:
    try:
        data = signing.loads(token, salt=SALT, max_age=settings.COUNTERPART_LINK_MAX_AGE)
    except signing.SignatureExpired as exc:
        raise ExpiredLink from exc
    except signing.BadSignature as exc:
        raise InvalidLink from exc
    request_id = data.get("r") if isinstance(data, dict) else None
    if not isinstance(request_id, int):
        raise InvalidLink
    return request_id
