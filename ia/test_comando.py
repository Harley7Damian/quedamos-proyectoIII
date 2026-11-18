"""Pruebas del comando de humo `probar_ia` (TR-80). Sin red: la IA esta simulada."""
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from .gemini import IaNoDisponible


class ProbarIaTests(SimpleTestCase):
    @override_settings(GEMINI_API_KEY="")
    def test_sin_clave_explica_que_falta(self):
        with self.assertRaisesMessage(CommandError, "GEMINI_API_KEY"):
            call_command("probar_ia")

    @override_settings(GEMINI_API_KEY="clave-de-prueba")
    def test_muestra_el_modelo_que_respondio(self):
        datos = {"asunto": "Revisar contrato", "duracion_min": 60, "contraparte": None, "semana": None, "dia": None}
        salida = StringIO()
        with mock.patch("ia.management.commands.probar_ia.pedir_json_detallado", return_value=(datos, "modelo-x")):
            call_command("probar_ia", stdout=salida)
        self.assertIn("Modelo que respondió: modelo-x", salida.getvalue())
        self.assertIn("La IA funciona.", salida.getvalue())

    @override_settings(GEMINI_API_KEY="clave-de-prueba")
    def test_si_la_ia_falla_el_comando_falla_con_el_motivo(self):
        with mock.patch("ia.management.commands.probar_ia.pedir_json_detallado", side_effect=IaNoDisponible()):
            with self.assertRaisesMessage(CommandError, "no respondió bien"):
                call_command("probar_ia")
