"""Configuracion de Quedamos. Los valores sensibles se leen de variables de entorno (.env)."""
import os
import sys
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEBUG = os.environ.get("DEBUG", "1") == "1"
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "clave-solo-para-desarrollo-local"
    else:
        raise RuntimeError("Falta la variable de entorno SECRET_KEY en produccion.")

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "meetings",
    "scheduling",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# SQLite en local. En produccion basta definir DATABASE_URL (PostgreSQL).
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Vigencia del enlace que se comparte con la contraparte (HU-05), en segundos.
COUNTERPART_LINK_MAX_AGE = int(os.environ.get("COUNTERPART_LINK_DAYS", "7")) * 24 * 3600
# Tamano maximo del archivo .ics que se importa para calcular la disponibilidad (TR-14), en bytes.
ICS_MAX_BYTES = 1024 * 1024
# Vigencia del enlace de aprobacion que recibe el ejecutivo (HU-08), en segundos. Mas corto porque las opciones caducan.
APPROVAL_LINK_MAX_AGE = int(os.environ.get("APPROVAL_LINK_DAYS", "3")) * 24 * 3600

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "panel"
LOGOUT_REDIRECT_URL = "login"

LANGUAGE_CODE = "es"
TIME_ZONE = "America/Lima"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Registros en consola con fecha, nivel, origen y mensaje (Render los recoge de la salida estandar).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "estandar": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "consola": {
            "class": "logging.StreamHandler",
            "formatter": "estandar",
            "level": os.environ.get("LOG_LEVEL", "INFO"),
        },
    },
    "root": {"handlers": ["consola"], "level": "DEBUG"},
}

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "1") == "1"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_REDIRECT_EXEMPT = [r"^salud/$"]  # la verificacion de salud de Render llega por HTTP interno
    # HSTS (TR-49): el navegador exigira HTTPS en este sitio durante HSTS_SECONDS. Se empieza con 1 hora
    # porque un valor largo es dificil de revertir. Se sube por variable de entorno (ver docs/CABECERA_HSTS.md).
    SECURE_HSTS_SECONDS = int(os.environ.get("HSTS_SECONDS", "3600"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True  # solo alcanza a subdominios de este mismo sitio, no a onrender.com

os.makedirs(STATIC_ROOT, exist_ok=True)  # evita el aviso de WhiteNoise en desarrollo

if "test" in sys.argv:
    # Hash rapido solo para las pruebas automaticas (nunca en uso normal).
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    LOGGING["handlers"]["consola"]["level"] = "CRITICAL"  # sin ruido en la salida de las pruebas
