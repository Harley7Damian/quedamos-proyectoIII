"""Pruebas de la llamada real de escalamiento por Twilio (TR-85)."""
from unittest import mock

from django.test import TestCase, override_settings

from .llamadas import hacer_llamada_recordatorio


class HacerLlamadaRecordatorioTests(TestCase):
    @override_settings(TWILIO_ACCOUNT_SID="", TWILIO_AUTH_TOKEN="", TWILIO_FROM_NUMBER="")
    def test_sin_credenciales_configuradas_devuelve_false(self):
        self.assertFalse(hacer_llamada_recordatorio("+51999999999", "hola"))

    @override_settings(
        TWILIO_ACCOUNT_SID="AC123", TWILIO_AUTH_TOKEN="token",
        TWILIO_FROM_NUMBER="+10000000000", SITE_URL="https://ejemplo.test",
    )
    @mock.patch("accounts.llamadas.Client")
    def test_credenciales_completas_llama_y_arma_bien_la_url(self, client_cls):
        ok = hacer_llamada_recordatorio("+51999999999", "hola mundo")
        self.assertTrue(ok)
        client_cls.return_value.calls.create.assert_called_once()
        _, kwargs = client_cls.return_value.calls.create.call_args
        self.assertEqual(kwargs["to"], "+51999999999")
        self.assertEqual(kwargs["from_"], "+10000000000")
        self.assertIn("https://ejemplo.test/telegram/llamada-twiml/?texto=", kwargs["url"])

    @override_settings(TWILIO_ACCOUNT_SID="AC123", TWILIO_AUTH_TOKEN="token", TWILIO_FROM_NUMBER="+10000000000")
    @mock.patch("accounts.llamadas.Client")
    def test_si_falla_twilio_devuelve_false_sin_lanzar_error(self, client_cls):
        client_cls.return_value.calls.create.side_effect = Exception("boom")
        ok = hacer_llamada_recordatorio("+51999999999", "hola")
        self.assertFalse(ok)
