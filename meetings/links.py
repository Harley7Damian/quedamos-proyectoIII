"""Enlaces firmados de la coordinacion: contraparte (HU-05) y aprobacion del ejecutivo (HU-08).

Ningun enlace guarda nada en la base de datos: lleva el id de la solicitud firmado con la
SECRET_KEY y una marca de tiempo. Si se altera o vence, deja de funcionar. Solo da acceso a esa
solicitud. Cada tipo de enlace usa una sal distinta, de modo que el enlace de la contraparte no
sirve para aprobar y el de aprobacion no sirve para registrar disponibilidad.
"""
from django.conf import settings
from django.core import signing

SALT = "quedamos.contraparte.v1"
APPROVAL_SALT = "quedamos.aprobacion.v1"


class InvalidLink(Exception):
    pass


class ExpiredLink(InvalidLink):
    pass


def _make(request_id: int, salt: str) -> str:
    return signing.dumps({"r": int(request_id)}, salt=salt)


def _read(token: str, salt: str, max_age: int) -> int:
    try:
        data = signing.loads(token, salt=salt, max_age=max_age)
    except signing.SignatureExpired as exc:
        raise ExpiredLink from exc
    except signing.BadSignature as exc:
        raise InvalidLink from exc
    request_id = data.get("r") if isinstance(data, dict) else None
    if not isinstance(request_id, int):
        raise InvalidLink
    return request_id


def make_token(request_id: int) -> str:
    return _make(request_id, SALT)


def read_token(token: str) -> int:
    return _read(token, SALT, settings.COUNTERPART_LINK_MAX_AGE)


def make_approval_token(request_id: int) -> str:
    return _make(request_id, APPROVAL_SALT)


def read_approval_token(token: str) -> int:
    return _read(token, APPROVAL_SALT, settings.APPROVAL_LINK_MAX_AGE)
