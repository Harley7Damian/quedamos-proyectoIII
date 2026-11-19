"""Pruebas de la vinculación y los recordatorios por Telegram (TR-73, TR-74)."""
import json
from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Profile, User
from .telegram import enviar_mensaje_telegram

PW = "Secreto-12345"


def mk(email, name, role):
    return User.objects.create_user(username=email, email=email, password=PW, full_name=name, role=role)


class TelegramBase(TestCase):
    def setUp(self):
        self.user = mk("carla@x.com", "Carla Ejecutiva", "ejecutivo")
        Profile.objects.create(user=self.user)

    def login(self):
        self.assertTrue(self.client.login(username=self.user.username, password=PW))

    def profile(self):
        return Profile.objects.get(user=self.user)


class GenerarCodigoTests(TelegramBase):
    def test_requiere_sesion(self):
        r = self.client.post(reverse("telegram_generar_codigo"))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith(reverse("login")))

    def test_solo_acepta_post(self):
        self.login()
        self.assertEqual(self.client.get(reverse("telegram_generar_codigo")).status_code, 405)

    def test_genera_un_codigo_con_vigencia(self):
        self.login()
        r = self.client.post(reverse("telegram_generar_codigo"), follow=True)
        p = self.profile()
        self.assertIsNotNone(p.telegram_link_code)
        self.assertIsNotNone(p.telegram_link_code_expira_en)
        self.assertTrue(p.telegram_link_code_vigente)
        self.assertContains(r, p.telegram_link_code)


class WebhookTests(TelegramBase):
    def post_mensaje(self, chat_id, texto):
        body = json.dumps({"message": {"chat": {"id": chat_id}, "text": texto}})
        return self.client.post(reverse("telegram_webhook"), data=body, content_type="application/json")

    @mock.patch("accounts.views.enviar_mensaje_telegram")
    def test_un_codigo_valido_vincula_el_chat_id(self, enviar_mock):
        p = self.profile()
        p.telegram_link_code = "ABC123"
        p.telegram_link_code_expira_en = timezone.now() + timedelta(minutes=5)
        p.save()

        r = self.post_mensaje(999888777, "/vincular ABC123")

        self.assertEqual(r.status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.telegram_chat_id, "999888777")
        self.assertIsNotNone(p.telegram_vinculado_en)
        self.assertIsNone(p.telegram_link_code)
        enviar_mock.assert_called_once()
        self.assertEqual(enviar_mock.call_args[0][0], "999888777")

    @mock.patch("accounts.views.enviar_mensaje_telegram")
    def test_un_codigo_ya_usado_no_vuelve_a_funcionar(self, enviar_mock):
        p = self.profile()
        p.telegram_link_code = "ABC123"
        p.telegram_link_code_expira_en = timezone.now() + timedelta(minutes=5)
        p.save()
        self.post_mensaje(111, "/vincular ABC123")

        r = self.post_mensaje(222, "/vincular ABC123")

        self.assertEqual(r.status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.telegram_chat_id, "111")  # sigue siendo el primero

    @mock.patch("accounts.views.enviar_mensaje_telegram")
    def test_un_codigo_expirado_no_vincula(self, enviar_mock):
        p = self.profile()
        p.telegram_link_code = "VIEJO1"
        p.telegram_link_code_expira_en = timezone.now() - timedelta(minutes=1)
        p.save()

        r = self.post_mensaje(333, "/vincular VIEJO1")

        self.assertEqual(r.status_code, 200)
        p.refresh_from_db()
        self.assertIsNone(p.telegram_chat_id)
        enviar_mock.assert_called_once_with("333", mock.ANY)

    @mock.patch("accounts.views.enviar_mensaje_telegram")
    def test_un_mensaje_sin_relacion_se_ignora(self, enviar_mock):
        r = self.post_mensaje(444, "hola, como estas?")
        self.assertEqual(r.status_code, 200)
        enviar_mock.assert_not_called()

    def test_json_invalido_da_400(self):
        r = self.client.post(reverse("telegram_webhook"), data="no es json", content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_solo_acepta_post(self):
        self.assertEqual(self.client.get(reverse("telegram_webhook")).status_code, 405)

    def test_rechaza_sin_el_secreto_correcto_cuando_esta_configurado(self):
        with self.settings(TELEGRAM_WEBHOOK_SECRET="un-secreto"):
            r = self.post_mensaje(123, "/vincular ABC123")
        self.assertEqual(r.status_code, 403)

    @mock.patch("accounts.views.enviar_mensaje_telegram")
    def test_acepta_con_el_secreto_correcto(self, enviar_mock):
        p = self.profile()
        p.telegram_link_code = "ABC123"
        p.telegram_link_code_expira_en = timezone.now() + timedelta(minutes=5)
        p.save()
        with self.settings(TELEGRAM_WEBHOOK_SECRET="un-secreto"):
            body = json.dumps({"message": {"chat": {"id": 123}, "text": "/vincular ABC123"}})
            r = self.client.post(
                reverse("telegram_webhook"), data=body, content_type="application/json",
                HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="un-secreto",
            )
        self.assertEqual(r.status_code, 200)


class DesvincularTests(TelegramBase):
    def test_requiere_sesion(self):
        r = self.client.post(reverse("telegram_desvincular"))
        self.assertEqual(r.status_code, 302)

    def test_borra_la_vinculacion(self):
        p = self.profile()
        p.telegram_chat_id = "555"
        p.telegram_vinculado_en = timezone.now()
        p.save()
        self.login()

        r = self.client.post(reverse("telegram_desvincular"), follow=True)

        p.refresh_from_db()
        self.assertIsNone(p.telegram_chat_id)
        self.assertIsNone(p.telegram_vinculado_en)
        self.assertContains(r, "Desvinculaste")


class EnviarMensajeTelegramTests(TestCase):
    @mock.patch("accounts.telegram.requests.post")
    def test_envio_exitoso_devuelve_true(self, post_mock):
        post_mock.return_value.raise_for_status.return_value = None
        with self.settings(TELEGRAM_BOT_TOKEN="token-de-prueba"):
            ok = enviar_mensaje_telegram("123", "hola")
        self.assertTrue(ok)
        post_mock.assert_called_once()

    @mock.patch("accounts.telegram.requests.post")
    def test_si_falla_el_envio_devuelve_false_sin_lanzar_error(self, post_mock):
        import requests
        post_mock.side_effect = requests.RequestException("sin conexión")
        with self.settings(TELEGRAM_BOT_TOKEN="token-de-prueba"):
            ok = enviar_mensaje_telegram("123", "hola")
        self.assertFalse(ok)

    def test_sin_token_configurado_devuelve_false(self):
        with self.settings(TELEGRAM_BOT_TOKEN=""):
            ok = enviar_mensaje_telegram("123", "hola")
        self.assertFalse(ok)

    @mock.patch("accounts.telegram.requests.post")
    def test_chat_id_invalido_devuelve_false_sin_lanzar_error(self, post_mock):
        import requests
        response = mock.Mock()
        response.raise_for_status.side_effect = requests.HTTPError("400 Client Error: Bad Request")
        post_mock.return_value = response
        with self.settings(TELEGRAM_BOT_TOKEN="token-de-prueba"):
            ok = enviar_mensaje_telegram("chat_id_invalido", "hola")
        self.assertFalse(ok)
