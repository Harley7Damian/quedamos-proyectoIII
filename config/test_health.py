"""Pruebas de la ruta de salud (TR-35) y del formato de los registros."""
import logging
from unittest import mock

from django.db import OperationalError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from accounts.models import User


class HealthTests(TestCase):
    def test_responde_200_con_la_base_de_datos_disponible(self):
        response = self.client.get("/salud/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"estado": "ok", "aplicacion": "ok", "base_de_datos": "ok"},
        )

    def test_la_ruta_es_publica_sin_iniciar_sesion(self):
        response = self.client.get("/salud/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Location", response)

    def test_acepta_head_y_rechaza_post(self):
        self.assertEqual(self.client.head("/salud/").status_code, 200)
        self.assertEqual(self.client.post("/salud/").status_code, 405)

    def test_no_se_guarda_en_cache(self):
        response = self.client.get("/salud/")
        self.assertIn("no-store", response["Cache-Control"])

    def test_responde_503_si_la_base_de_datos_falla(self):
        with mock.patch("config.health.connection") as conexion:
            conexion.cursor.side_effect = OperationalError("falla simulada con detalle interno")
            with self.assertLogs("config.health", level="ERROR"):
                response = self.client.get("/salud/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"estado": "error", "aplicacion": "ok", "base_de_datos": "error"},
        )

    def test_el_error_se_registra_sin_detalles_internos(self):
        with mock.patch("config.health.connection") as conexion:
            conexion.cursor.side_effect = OperationalError("falla simulada con detalle interno")
            with self.assertLogs("config.health", level="ERROR") as registro:
                response = self.client.get("/salud/")
        salida = "\n".join(registro.output)
        self.assertIn("la base de datos no responde", salida)
        self.assertIn("OperationalError", salida)
        self.assertNotIn("detalle interno", salida)
        self.assertNotIn("detalle interno", response.content.decode())

    def test_la_respuesta_no_incluye_datos_de_usuarios(self):
        User.objects.create_user(username="ana", email="ana@empresa.pe", password="Secreto-12345")
        cuerpo = self.client.get("/salud/").content.decode()
        self.assertNotIn("ana", cuerpo)
        self.assertNotIn("empresa.pe", cuerpo)

    def test_el_nombre_de_la_ruta_apunta_a_salud(self):
        self.assertEqual(reverse("health"), "/salud/")


class LoggingFormatTests(SimpleTestCase):
    def test_el_registro_raiz_usa_el_formato_con_fecha_nivel_origen_y_mensaje(self):
        formatos = [
            handler.formatter._fmt
            for handler in logging.getLogger().handlers
            if handler.formatter is not None
        ]
        self.assertIn("%(asctime)s %(levelname)s %(name)s %(message)s", formatos)

    def test_un_registro_se_escribe_con_el_formato_esperado(self):
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        registro = logging.LogRecord("config.health", logging.ERROR, __file__, 1, "mensaje de prueba", None, None)
        self.assertRegex(
            formatter.format(registro),
            r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} ERROR config\.health mensaje de prueba$",
        )
