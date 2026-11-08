"""Pruebas de la cabecera HSTS (TR-49).

La cabecera solo se activa en producción (DEBUG=0), así que se comprueba en un proceso aparte que arranca la
aplicación con esa configuración, sin tocar la configuración de las demás pruebas.
"""
import os
import re
import secrets
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase

CODIGO = """
import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()
from django.test import Client
respuesta = Client().get('/acceso/', secure=True)
print('STS=' + str(respuesta.headers.get('Strict-Transport-Security')))
"""


def proceso(*argumentos, debug="0", hsts=None):
    """Ejecuta Python con la configuración indicada y devuelve su salida."""
    entorno = dict(os.environ, DEBUG=debug, SECRET_KEY=secrets.token_urlsafe(60), ALLOWED_HOSTS="testserver,localhost",
                   DATABASE_URL="sqlite:///:memory:")
    entorno.pop("HSTS_SECONDS", None)
    if hsts is not None:
        entorno["HSTS_SECONDS"] = str(hsts)
    resultado = subprocess.run([sys.executable, *argumentos], cwd=settings.BASE_DIR, env=entorno,
                               capture_output=True, text=True, timeout=120)
    return resultado.stdout + resultado.stderr


def cabecera(**opciones):
    salida = proceso("-c", CODIGO, **opciones)
    return re.search(r"STS=(.*)", salida).group(1).strip()


class CabeceraHstsTests(SimpleTestCase):
    def test_en_produccion_la_respuesta_https_incluye_hsts_con_una_hora_por_defecto(self):
        self.assertEqual(cabecera(), "max-age=3600; includeSubDomains")

    def test_la_vigencia_se_define_con_una_variable_de_entorno(self):
        self.assertEqual(cabecera(hsts=86400), "max-age=86400; includeSubDomains")

    def test_para_revertir_se_envia_una_vigencia_de_un_segundo(self):
        self.assertEqual(cabecera(hsts=1), "max-age=1; includeSubDomains")

    def test_con_cero_se_deja_de_enviar_la_cabecera(self):
        self.assertEqual(cabecera(hsts=0), "None")

    def test_en_desarrollo_no_se_envia_hsts(self):
        self.assertEqual(cabecera(debug="1"), "None")

    def test_check_deploy_ya_no_muestra_la_advertencia_w004(self):
        salida = proceso("manage.py", "check", "--deploy")
        self.assertNotIn("security.W004", salida)
        self.assertNotIn("security.W005", salida)

    def test_check_deploy_sin_hsts_si_la_mostraba(self):
        salida = proceso("manage.py", "check", "--deploy", hsts=0)
        self.assertIn("security.W004", salida)
