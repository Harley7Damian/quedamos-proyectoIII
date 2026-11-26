"""Validación estricta de correos (registro y solicitudes).

Va más allá del formato de Django: exige un dominio con punto y una terminación real, y detecta
los errores de tipeo más comunes ("gmial.com", "empresa.con") con una sugerencia para corregirlos.
No comprueba que el buzón exista: eso solo lo prueba un mensaje real, que requiere un proveedor de correo."""
import re

from django.core.exceptions import ValidationError

# Errores frecuentes en los dominios más usados, con el dominio correcto.
DOMINIOS_CON_ERROR = {
    "gmial.com": "gmail.com", "gmai.com": "gmail.com", "gamil.com": "gmail.com", "gmaill.com": "gmail.com",
    "gnail.com": "gmail.com", "gmail.con": "gmail.com", "gmail.cm": "gmail.com", "gmail.co": "gmail.com",
    "gmail.om": "gmail.com", "gmeil.com": "gmail.com", "gmail.comm": "gmail.com",
    "hotmial.com": "hotmail.com", "hotmai.com": "hotmail.com", "hotmil.com": "hotmail.com",
    "hotmail.con": "hotmail.com", "hotmail.cm": "hotmail.com", "hotmaill.com": "hotmail.com",
    "outlok.com": "outlook.com", "otlook.com": "outlook.com", "outlook.con": "outlook.com", "outllok.com": "outlook.com",
    "yaho.com": "yahoo.com", "yahooo.com": "yahoo.com", "yahoo.con": "yahoo.com", "yahoo.cm": "yahoo.com",
    "icloud.con": "icloud.com", "iclod.com": "icloud.com", "icoud.com": "icloud.com",
    "usil.edu.p": "usil.edu.pe", "usil.edu.per": "usil.edu.pe",
}
# Terminaciones mal escritas de ".com" en cualquier dominio.
TERMINACIONES_CON_ERROR = {"con", "cim", "vom", "xom", "coom", "comm", "c0m", "cpm", "ocm"}

_LOCAL = re.compile(r"^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+$")
_ETIQUETA = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")


def sugerencia_de_dominio(dominio: str) -> str:
    """Devuelve el dominio corregido si parece un error de tipeo, o '' si no lo parece."""
    if dominio in DOMINIOS_CON_ERROR:
        return DOMINIOS_CON_ERROR[dominio]
    base, _, terminacion = dominio.rpartition(".")
    if base and terminacion in TERMINACIONES_CON_ERROR:
        return f"{base}.com"
    return ""


def validar_correo(valor: str) -> str:
    """Devuelve el correo limpio y en minúsculas, o lanza ValidationError con un mensaje claro."""
    correo = (valor or "").strip().lower()
    if not correo:
        return ""
    if len(correo) > 150 or correo.count("@") != 1:
        raise ValidationError("Escribe un correo con el formato nombre@empresa.com.")
    local, dominio = correo.split("@")
    etiquetas = dominio.split(".")
    if (
        not local or len(local) > 64 or not _LOCAL.match(local) or ".." in local
        or local.startswith(".") or local.endswith(".")
    ):
        raise ValidationError("La parte antes de la arroba no parece válida. Revisa el correo.")
    if len(etiquetas) < 2 or not all(_ETIQUETA.match(e) for e in etiquetas):
        raise ValidationError("El dominio del correo no parece válido. Revisa lo que está después de la arroba.")
    sugerido = sugerencia_de_dominio(dominio)
    if sugerido:
        raise ValidationError(f"¿Quisiste decir {local}@{sugerido}? Revisa cómo escribiste el dominio.")
    if not re.fullmatch(r"[a-z]{2,24}", etiquetas[-1]):
        raise ValidationError("La terminación del correo no parece válida. Por ejemplo .com o .pe.")
    return correo
