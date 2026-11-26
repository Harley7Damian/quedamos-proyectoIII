"""Validación estricta de correos (registro y solicitudes).

Simula lo esencial de lo que haría un proveedor de correo antes de aceptar una dirección:
  1. formato correcto (una arroba, caracteres permitidos, dominio con punto y terminación real);
  2. reglas propias de los proveedores conocidos (Gmail, Outlook, Hotmail, Yahoo, iCloud);
  3. dominios de ejemplo o temporales rechazados (example.com, mailinator.com);
  4. errores de tipeo con sugerencia ("gmial.com", "usli.edu.pe", "empresa.con");
  5. dominios institucionales (.edu.pe, .gob.pe) que deben nombrar a la institución;
  6. opcionalmente, que el dominio exista de verdad en internet (consulta DNS), con CORREO_VERIFICAR_DNS=1.

Lo que NO puede probar es que el buzón exista ni que la persona sea su dueña: eso solo lo prueba un mensaje
real con un enlace de confirmación, que requiere un proveedor de correo."""
import re
import socket

from django.conf import settings
from django.core.exceptions import ValidationError

# ------------------------------------------------------------------ datos

# Errores frecuentes con el dominio correcto (además de la comparación aproximada de más abajo).
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

# Proveedores públicos: nombre -> dominio principal. Un dominio que empieza con ese nombre pero no es uno
# de los reales (gmail.es, gmail.pe) casi siempre es un error de tipeo.
PROVEEDORES = {
    "gmail": "gmail.com", "hotmail": "hotmail.com", "outlook": "outlook.com", "yahoo": "yahoo.com",
    "icloud": "icloud.com", "live": "live.com", "msn": "msn.com", "protonmail": "protonmail.com", "aol": "aol.com",
}
# Países en los que Microsoft y Yahoo tienen dominio propio (hotmail.es, outlook.com.pe, yahoo.com.mx...).
_SUFIJOS_REGIONALES = {
    "com", "es", "fr", "de", "it", "co.uk", "com.pe", "com.mx", "com.ar", "com.co", "cl", "com.br", "ca", "co.jp",
    "com.au", "nl", "pt",
}
DOMINIOS_PUBLICOS = (
    {"gmail.com", "googlemail.com", "icloud.com", "me.com", "mac.com", "msn.com", "ymail.com", "rocketmail.com",
     "aol.com", "proton.me", "protonmail.com", "pm.me", "gmx.com", "gmx.net", "gmx.es", "zoho.com", "yandex.com",
     "mail.com", "email.com", "fastmail.com", "live.com"}
    | {f"{n}.{s}" for n in ("hotmail", "outlook", "live", "yahoo") for s in _SUFIJOS_REGIONALES}
)

# Instituciones educativas y públicas del Perú que los usuarios de Quedamos pueden usar. Sirve para aceptar sin
# más sus dominios y para sugerir el correcto cuando alguien escribe una variante cercana ("usli.edu.pe").
INSTITUCIONES = {
    "usil", "pucp", "up", "ulima", "upc", "upn", "utp", "utec", "esan", "uni", "unmsm", "unac", "unfv", "unalm",
    "uncp", "unsa", "unt", "unsaac", "uarm", "ucv", "uss", "usat", "ucsm", "ucss", "upch", "usmp", "urp", "uap",
    "uigv", "ucal", "cibertec", "tecsup", "senati", "continental", "ucontinental", "wiener", "uwiener", "ulasalle",
    "pacifico", "lasalle", "unife", "unh", "unprg", "unap", "unsch", "unjbg", "unasam", "unu", "untels",
}
_SUFIJOS_INSTITUCIONALES = ("edu.pe", "gob.pe")

# Dominios de ejemplo, de prueba o que no reciben correo (RFC 2606) y marcadores de posición.
DOMINIOS_DE_EJEMPLO = {
    "example.com", "example.org", "example.net", "example.edu", "domain.com", "dominio.com", "ejemplo.com",
    "test.com", "prueba.com", "email.test", "sample.com", "correo.com", "tucorreo.com", "tuempresa.com",
}
_ETIQUETAS_RESERVADAS = {"test", "invalid", "localhost", "local", "example", "invalido", "prueba"}

# Servicios de correo temporal o desechable.
DOMINIOS_DESECHABLES = {
    "mailinator.com", "guerrillamail.com", "guerrillamail.net", "guerrillamail.org", "guerrillamail.biz",
    "guerrillamail.de", "guerrillamailblock.com", "sharklasers.com", "grr.la", "spam4.me", "10minutemail.com",
    "10minutemail.net", "tempmail.com", "temp-mail.org", "temp-mail.io", "tempmail.net", "tempail.com",
    "yopmail.com", "yopmail.fr", "trashmail.com", "trashmail.net", "getnada.com", "nada.email", "throwawaymail.com",
    "maildrop.cc", "dispostable.com", "fakeinbox.com", "mailnesia.com", "mohmal.com", "emailondeck.com",
    "burnermail.io", "moakt.com", "mytemp.email", "tmpmail.org", "mintemail.com", "inboxkitten.com",
    "dropmail.me", "mailcatch.com", "tempinbox.com", "jetable.org", "discard.email", "fakemail.net",
    "minuteinbox.com", "emailfake.com", "mailtemp.net", "tempr.email", "harakirimail.com",
}

# Terminaciones de dominio válidas: las genéricas más usadas y todos los países.
_TLD_GENERICOS = {
    "com", "net", "org", "edu", "gov", "mil", "int", "info", "biz", "name", "pro", "mobi", "asia", "travel", "tel",
    "museum", "aero", "coop", "io", "app", "dev", "ai", "tech", "online", "site", "xyz", "cloud", "store", "shop",
    "group", "company", "email", "global", "world", "studio", "agency", "digital", "network", "systems", "services",
    "solutions", "consulting", "capital", "finance", "bank", "insurance", "health", "university", "school", "academy",
    "education", "institute", "foundation", "ngo", "ong", "club", "live", "life", "today", "space", "website", "link",
    "one", "team", "work", "ventures", "partners", "legal", "law", "media", "news", "design", "software", "labs",
    "lat", "engineering", "energy", "industries", "logistics", "trade", "market", "marketing", "money", "tax",
}
_TLD_PAISES = set(
    "ac ad ae af ag ai al am ao aq ar as at au aw ax az ba bb bd be bf bg bh bi bj bm bn bo br bs bt bw by bz ca cc "
    "cd cf cg ch ci ck cl cm cn co cr cu cv cw cx cy cz de dj dk dm do dz ec ee eg er es et eu fi fj fk fm fo fr ga "
    "gd ge gf gg gh gi gl gm gn gp gq gr gs gt gu gw gy hk hm hn hr ht hu id ie il im in io iq ir is it je jm jo jp "
    "ke kg kh ki km kn kp kr kw ky kz la lb lc li lk lr ls lt lu lv ly ma mc md me mg mh mk ml mm mn mo mp mq mr ms "
    "mt mu mv mw mx my mz na nc ne nf ng ni nl no np nr nu nz om pa pe pf pg ph pk pl pm pn pr ps pt pw py qa re ro "
    "rs ru rw sa sb sc sd se sg sh si sk sl sm sn so sr ss st su sv sx sy sz tc td tf tg th tj tk tl tm tn to tr tt "
    "tv tw tz ua ug uk us uy uz va vc ve vg vi vn vu wf ws ye yt za zm zw".split()
)
TERMINACIONES_VALIDAS = _TLD_GENERICOS | _TLD_PAISES
# "com.pe", "edu.pe", "co.uk"...: son terminaciones, no dominios; falta el nombre de la empresa o institución.
_SEGUNDO_NIVEL = {"com", "edu", "gob", "gov", "org", "net", "mil", "ac", "co", "nom"}

# Nombres de usuario que delatan un correo inventado.
_LOCALES_FALSOS = {
    "test", "tests", "testing", "tester", "prueba", "pruebas", "ejemplo", "example", "correo", "email", "mail",
    "nombre", "usuario", "user", "asdf", "asdfg", "asdfgh", "asdfghj", "asd", "asdasd", "qwe", "qwer", "qwerty",
    "qwertyuiop", "zxcv", "zxcvbn", "abc", "abcd", "abcde", "abcdef", "abcdefg", "xyz", "xxx", "xxxx", "fake",
    "falso", "nada", "ninguno", "noexiste", "none", "null", "no", "si", "hola", "hello", "aaa", "aaaa", "sdf", "sdfsdf",
    "123", "1234", "12345", "123456", "1234567", "12345678", "123456789", "0000", "00000", "000000", "111111",
}

_LOCAL = re.compile(r"^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+$")
_ETIQUETA = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")


# ------------------------------------------------------------------ utilidades

def _distancia(a: str, b: str) -> int:
    """Distancia de edición con transposición de letras vecinas (gmial -> gmail vale 1)."""
    previa2, previa = None, list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        actual = [i]
        for j, cb in enumerate(b, 1):
            costo = 0 if ca == cb else 1
            valor = min(previa[j] + 1, actual[j - 1] + 1, previa[j - 1] + costo)
            if previa2 is not None and i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                valor = min(valor, previa2[j - 2] + 1)
            actual.append(valor)
        previa2, previa = previa, actual
    return previa[-1]


def _es_dominio_publico(dominio: str) -> bool:
    return dominio in DOMINIOS_PUBLICOS


def _etiqueta_institucional(etiquetas: list[str]) -> str:
    """Nombre de la institución en un dominio .edu.pe o .gob.pe (usil en 'mail.usil.edu.pe'), o ''."""
    if len(etiquetas) >= 3 and ".".join(etiquetas[-2:]) in _SUFIJOS_INSTITUCIONALES:
        return etiquetas[-3]
    return ""


def sugerencia_de_dominio(dominio: str) -> str:
    """Devuelve el dominio corregido si parece un error de tipeo, o '' si no lo parece."""
    if dominio in DOMINIOS_CON_ERROR:
        return DOMINIOS_CON_ERROR[dominio]
    etiquetas = dominio.split(".")
    nombre = etiquetas[0]
    if not _es_dominio_publico(dominio):
        # gmail.es, hotmail.pe, yahoo.org...: el nombre es de un proveedor pero el dominio no existe.
        if nombre in PROVEEDORES:
            return PROVEEDORES[nombre]
        # gmial.com, hotmal.es, outlok.com...: una letra cambiada, faltante o repetida.
        if len(etiquetas) <= 3:
            for conocido, principal in PROVEEDORES.items():
                if len(conocido) >= 5 and _distancia(nombre, conocido) == 1 and not _es_dominio_publico(f"{nombre}.com"):
                    return principal
    institucion = _etiqueta_institucional(etiquetas)
    if institucion and institucion not in INSTITUCIONES and len(institucion) >= 4:
        for conocida in INSTITUCIONES:
            if len(conocida) >= 4 and _distancia(institucion, conocida) == 1:
                return ".".join([*etiquetas[:-3], conocida, *etiquetas[-2:]])
    base, _, terminacion = dominio.rpartition(".")
    if base and terminacion in TERMINACIONES_CON_ERROR:
        return f"{base}.com"
    return ""


# ------------------------------------------------------------------ reglas de cada proveedor

def _reglas_gmail(base: str):
    if not 6 <= len(base) <= 30:
        return "Una dirección de Gmail tiene entre 6 y 30 caracteres antes de la arroba."
    if not re.fullmatch(r"[a-z0-9.]+", base):
        return "Una dirección de Gmail solo admite letras, números y puntos antes de la arroba."
    if base.startswith(".") or base.endswith("."):
        return "Una dirección de Gmail no puede empezar ni terminar con punto antes de la arroba."
    return ""


def _reglas_microsoft(base: str):
    if not re.fullmatch(r"[a-z0-9._-]{1,64}", base):
        return "Una dirección de Outlook o Hotmail solo admite letras, números, puntos, guiones y guiones bajos."
    if not re.search(r"[a-z]", base):
        return "Una dirección de Outlook o Hotmail debe incluir letras, no solo números."
    return ""


def _reglas_yahoo(base: str):
    if not 4 <= len(base) <= 32:
        return "Una dirección de Yahoo tiene entre 4 y 32 caracteres antes de la arroba."
    if not re.fullmatch(r"[a-z][a-z0-9._]*", base) or base.count(".") > 1 or base[-1] in "._":
        return "Una dirección de Yahoo empieza con una letra y solo admite letras, números, guiones bajos y un punto."
    return ""


def _reglas_icloud(base: str):
    if len(base) < 3 or not re.fullmatch(r"[a-z][a-z0-9._]*", base):
        return ("Una dirección de iCloud empieza con una letra, tiene al menos 3 caracteres "
                "y solo admite letras, números, puntos y guiones bajos.")
    return ""


def _regla_del_proveedor(dominio: str):
    """Devuelve (función de reglas, admite_alias_con_más) para el dominio, o None si no tiene reglas propias."""
    nombre = dominio.split(".")[0]
    if dominio in ("gmail.com", "googlemail.com"):
        return _reglas_gmail, True
    if nombre in ("hotmail", "outlook", "live", "msn") and _es_dominio_publico(dominio):
        return _reglas_microsoft, True
    if dominio in ("ymail.com", "rocketmail.com") or (nombre == "yahoo" and _es_dominio_publico(dominio)):
        return _reglas_yahoo, False
    if dominio in ("icloud.com", "me.com", "mac.com"):
        return _reglas_icloud, False
    return None


# ------------------------------------------------------------------ existencia del dominio (opcional)

def _dominio_existe(dominio: str) -> bool:
    """Consulta DNS: el dominio debe existir y poder recibir correo. Ante un fallo de red acepta (no bloquea)."""
    try:
        import dns.exception
        import dns.resolver
    except ImportError:  # sin dnspython se comprueba al menos que el nombre resuelva
        try:
            socket.getaddrinfo(dominio, None)
            return True
        except socket.gaierror as exc:
            return exc.errno not in (socket.EAI_NONAME, getattr(socket, "EAI_NODATA", socket.EAI_NONAME))
        except OSError:
            return True
    try:
        dns.resolver.resolve(dominio, "MX", lifetime=3)
        return True
    except dns.resolver.NXDOMAIN:
        return False
    except dns.resolver.NoAnswer:
        pass  # sin registro MX, el correo puede ir al registro A del dominio
    except dns.exception.DNSException:
        return True
    try:
        dns.resolver.resolve(dominio, "A", lifetime=3)
        return True
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return False
    except dns.exception.DNSException:
        return True


# ------------------------------------------------------------------ validación

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

    # Dominios que no sirven: de ejemplo, reservados o temporales.
    if dominio in DOMINIOS_DE_EJEMPLO or etiquetas[-1] in _ETIQUETAS_RESERVADAS:
        raise ValidationError("Ese dominio es de ejemplo. Escribe el correo real de la persona.")
    if dominio in DOMINIOS_DESECHABLES or ".".join(etiquetas[-2:]) in DOMINIOS_DESECHABLES:
        raise ValidationError("No se aceptan correos temporales. Escribe el correo habitual de la persona.")

    # Errores de tipeo con sugerencia.
    sugerido = sugerencia_de_dominio(dominio)
    if sugerido:
        raise ValidationError(f"¿Quisiste decir {local}@{sugerido}? Revisa cómo escribiste el dominio.")

    # Terminación real y dominio con nombre propio (no solo "com.pe" o "edu.pe").
    if not re.fullmatch(r"[a-z]{2,24}", etiquetas[-1]) or etiquetas[-1] not in TERMINACIONES_VALIDAS:
        raise ValidationError("La terminación del correo no parece válida. Por ejemplo .com o .pe.")
    if len(etiquetas) == 2 and etiquetas[0] in _SEGUNDO_NIVEL and len(etiquetas[1]) == 2:
        raise ValidationError(f"Falta el nombre de la empresa o institución antes de @{dominio}. Por ejemplo, usil.{dominio}.")

    # Nombre de usuario inventado.
    base_local = local.split("+")[0]
    if len(base_local) < 2 or base_local in _LOCALES_FALSOS or re.fullmatch(r"(.)\1{2,}", base_local):
        raise ValidationError("Ese nombre antes de la arroba parece de prueba. Escribe el correo real de la persona.")

    # Reglas propias del proveedor (Gmail, Outlook, Hotmail, Yahoo, iCloud).
    regla = _regla_del_proveedor(dominio)
    if regla:
        funcion, admite_alias = regla
        error = funcion(base_local if admite_alias else local)
        if error:
            raise ValidationError(error)
        return correo
    if _es_dominio_publico(dominio):
        return correo

    # Institucional: debe nombrar a la institución (usil.edu.pe, minedu.gob.pe).
    institucion = _etiqueta_institucional(etiquetas)
    if institucion and institucion in INSTITUCIONES:
        return correo

    # Dominio desconocido: si se activó la consulta DNS, debe existir de verdad.
    if getattr(settings, "CORREO_VERIFICAR_DNS", False) and not _dominio_existe(dominio):
        raise ValidationError(f"No encontramos el dominio {dominio}. Revisa que esté bien escrito.")
    return correo
