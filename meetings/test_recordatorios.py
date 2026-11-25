"""Pruebas del comando que envia los recordatorios de Telegram (TR-76/TR-79)."""
from datetime import date, datetime, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.test import TestCase

from accounts.models import Profile, User

from .models import MeetingRequest

LIMA = ZoneInfo("America/Lima")
PW = "Secreto-12345"


def mk(email, name, role):
    return User.objects.create_user(username=email, email=email, password=PW, full_name=name, role=role)


class EnviarRecordatoriosTests(TestCase):
    def setUp(self):
        self.ejec = mk("carla@x.com", "Carla Ejecutiva", "ejecutivo")
        self.asis = mk("ana@x.com", "Ana Asistente", "asistente")
        Profile.objects.create(user=self.ejec, telegram_chat_id="111")
        Profile.objects.create(user=self.asis, telegram_chat_id="222")
        self.ahora = datetime(2026, 11, 20, 10, 0, tzinfo=LIMA)

    def crear_solicitud(self, minutos_para_empezar, status=MeetingRequest.Status.APROBADA):
        inicio = self.ahora + timedelta(minutes=minutos_para_empezar)
        return MeetingRequest.objects.create(
            executive=self.ejec, created_by=self.asis, title="Revisión", counterpart_name="Pedro Gómez",
            duration_min=30, week_start=date(2026, 11, 23), status=status,
            approved_start=inicio, approved_end=inicio + timedelta(minutes=30),
        )

    def correr_comando(self):
        patcher = mock.patch("django.utils.timezone.now", return_value=self.ahora)
        patcher.start()
        self.addCleanup(patcher.stop)
        call_command("enviar_recordatorios")

    @mock.patch("meetings.management.commands.enviar_recordatorios.enviar_mensaje_telegram")
    def test_envia_el_recordatorio_de_30_minutos_al_ejecutivo_y_a_la_asistente(self, enviar_mock):
        self.crear_solicitud(minutos_para_empezar=30)
        self.correr_comando()
        self.assertEqual(enviar_mock.call_count, 2)
        chats = {llamada.args[0] for llamada in enviar_mock.call_args_list}
        self.assertEqual(chats, {"111", "222"})

    @mock.patch("meetings.management.commands.enviar_recordatorios.enviar_mensaje_telegram")
    def test_envia_el_recordatorio_de_5_minutos(self, enviar_mock):
        self.crear_solicitud(minutos_para_empezar=5)
        self.correr_comando()
        self.assertEqual(enviar_mock.call_count, 2)

    @mock.patch("meetings.management.commands.enviar_recordatorios.enviar_mensaje_telegram")
    def test_no_duplica_el_mismo_recordatorio(self, enviar_mock):
        self.crear_solicitud(minutos_para_empezar=30)
        self.correr_comando()
        self.correr_comando()
        self.assertEqual(enviar_mock.call_count, 2)  # no 4

    @mock.patch("meetings.management.commands.enviar_recordatorios.enviar_mensaje_telegram")
    def test_no_envia_a_quien_no_vinculo_telegram(self, enviar_mock):
        Profile.objects.filter(user=self.asis).update(telegram_chat_id=None)
        self.crear_solicitud(minutos_para_empezar=30)
        self.correr_comando()
        self.assertEqual(enviar_mock.call_count, 1)
        self.assertEqual(enviar_mock.call_args.args[0], "111")

    @mock.patch("meetings.management.commands.enviar_recordatorios.enviar_mensaje_telegram")
    def test_ignora_reuniones_no_aprobadas(self, enviar_mock):
        self.crear_solicitud(minutos_para_empezar=30, status=MeetingRequest.Status.PENDIENTE)
        self.correr_comando()
        enviar_mock.assert_not_called()

    @mock.patch("meetings.management.commands.enviar_recordatorios.enviar_mensaje_telegram")
    def test_ignora_reuniones_muy_lejanas(self, enviar_mock):
        self.crear_solicitud(minutos_para_empezar=45)
        self.correr_comando()
        enviar_mock.assert_not_called()

    @mock.patch("meetings.management.commands.enviar_recordatorios.enviar_mensaje_telegram")
    def test_envia_el_de_30_aunque_la_reunion_se_haya_creado_tarde(self, enviar_mock):
        """Caso borde real (TR-79): la reunión se crea cuando ya faltan menos de
        30 minutos (p. ej. 27). Antes esto hacía que el recordatorio de 30 min se
        perdiera para siempre; ahora debe enviarse en la siguiente corrida."""
        self.crear_solicitud(minutos_para_empezar=27)
        self.correr_comando()
        self.assertEqual(enviar_mock.call_count, 2)

    @mock.patch("meetings.management.commands.enviar_recordatorios.enviar_mensaje_telegram")
    def test_envia_el_de_5_aunque_el_cron_se_haya_atrasado(self, enviar_mock):
        """Caso borde real (TR-79): el cron no corrió justo en el minuto exacto
        (p. ej. faltan 3 minutos, no 5). Debe seguir enviando el recordatorio de
        5 minutos mientras la reunión no haya empezado."""
        self.crear_solicitud(minutos_para_empezar=3)
        self.correr_comando()
        self.assertEqual(enviar_mock.call_count, 2)

    @mock.patch("meetings.management.commands.enviar_recordatorios.enviar_mensaje_telegram")
    def test_no_envia_si_la_reunion_ya_empezo(self, enviar_mock):
        self.crear_solicitud(minutos_para_empezar=-5)
        self.correr_comando()
        enviar_mock.assert_not_called()

    @mock.patch("meetings.management.commands.enviar_recordatorios.enviar_mensaje_telegram")
    def test_un_error_en_una_solicitud_no_detiene_a_las_demas(self, enviar_mock):
        """Caso borde (TR-79): si falla el envío de una reunión (p. ej. Telegram
        no responde), las demás reuniones de la misma corrida deben seguir
        procesándose igual."""
        self.crear_solicitud(minutos_para_empezar=30)
        otra = self.crear_solicitud(minutos_para_empezar=30)
        enviar_mock.side_effect = [Exception("boom"), None, None, None]
        self.correr_comando()
        otra.refresh_from_db()
        self.assertIsNotNone(otra.recordatorio_30_enviado_en)

class EscalamientoPorLlamadaTests(TestCase):
    """TR-85: si no confirmaron /visto, además de Telegram se hace una llamada real."""

    def setUp(self):
        self.ejec = mk("carla_llamada@x.com", "Carla Llamada", "ejecutivo")
        self.asis = mk("ana_llamada@x.com", "Ana Llamada", "asistente")
        self.perfil_ejec = Profile.objects.create(user=self.ejec, telegram_chat_id="111", telefono="+51999999999")
        Profile.objects.create(user=self.asis, telegram_chat_id="222")
        self.ahora = datetime(2026, 11, 20, 10, 0, tzinfo=LIMA)

    def crear_solicitud(self, minutos_para_empezar, confirmado_en=None):
        inicio = self.ahora + timedelta(minutes=minutos_para_empezar)
        return MeetingRequest.objects.create(
            executive=self.ejec, created_by=self.asis, title="Revisión", counterpart_name="Pedro Gómez",
            duration_min=30, week_start=date(2026, 11, 23), status=MeetingRequest.Status.APROBADA,
            approved_start=inicio, approved_end=inicio + timedelta(minutes=30),
            confirmado_en=confirmado_en,
        )

    def correr_comando(self):
        patcher = mock.patch("django.utils.timezone.now", return_value=self.ahora)
        patcher.start()
        self.addCleanup(patcher.stop)
        call_command("enviar_recordatorios")

    @mock.patch("meetings.management.commands.enviar_recordatorios.hacer_llamada_recordatorio")
    @mock.patch("meetings.management.commands.enviar_recordatorios.enviar_mensaje_telegram")
    def test_llama_si_no_confirmo_y_tiene_telefono(self, enviar_mock, llamada_mock):
        self.crear_solicitud(minutos_para_empezar=3, confirmado_en=None)
        self.correr_comando()
        llamada_mock.assert_called_once()
        args, kwargs = llamada_mock.call_args
        self.assertEqual(args[0], "+51999999999")

    @mock.patch("meetings.management.commands.enviar_recordatorios.hacer_llamada_recordatorio")
    @mock.patch("meetings.management.commands.enviar_recordatorios.enviar_mensaje_telegram")
    def test_no_llama_si_ya_confirmo_con_visto(self, enviar_mock, llamada_mock):
        self.crear_solicitud(minutos_para_empezar=3, confirmado_en=self.ahora)
        self.correr_comando()
        llamada_mock.assert_not_called()

    @mock.patch("meetings.management.commands.enviar_recordatorios.hacer_llamada_recordatorio")
    @mock.patch("meetings.management.commands.enviar_recordatorios.enviar_mensaje_telegram")
    def test_no_llama_si_no_tiene_telefono(self, enviar_mock, llamada_mock):
        self.perfil_ejec.telefono = ""
        self.perfil_ejec.save(update_fields=["telefono"])
        self.crear_solicitud(minutos_para_empezar=3, confirmado_en=None)
        self.correr_comando()
        llamada_mock.assert_not_called()

    @mock.patch("meetings.management.commands.enviar_recordatorios.hacer_llamada_recordatorio")
    @mock.patch("meetings.management.commands.enviar_recordatorios.enviar_mensaje_telegram")
    def test_llama_con_un_texto_limpio_pensado_para_voz(self, enviar_mock, llamada_mock):
        self.crear_solicitud(minutos_para_empezar=3, confirmado_en=None)
        self.correr_comando()
        llamada_mock.assert_called_once()
        args, kwargs = llamada_mock.call_args
        texto_voz = args[1]
        self.assertNotIn("/visto", texto_voz)
        self.assertNotIn("http", texto_voz)
