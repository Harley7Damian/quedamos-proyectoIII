"""Pruebas del comando que envia los recordatorios de Telegram (TR-76)."""
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
    def test_ignora_reuniones_fuera_de_la_ventana(self, enviar_mock):
        self.crear_solicitud(minutos_para_empezar=45)
        self.correr_comando()
        enviar_mock.assert_not_called()

    @mock.patch("meetings.management.commands.enviar_recordatorios.enviar_mensaje_telegram")
    def test_no_envia_un_minuto_antes_del_limite_de_30(self, enviar_mock):
        self.crear_solicitud(minutos_para_empezar=29)
        self.correr_comando()
        enviar_mock.assert_not_called()

    @mock.patch("meetings.management.commands.enviar_recordatorios.enviar_mensaje_telegram")
    def test_no_envia_un_minuto_despues_del_limite_de_30(self, enviar_mock):
        self.crear_solicitud(minutos_para_empezar=31)
        self.correr_comando()
        enviar_mock.assert_not_called()

    @mock.patch("meetings.management.commands.enviar_recordatorios.enviar_mensaje_telegram")
    def test_no_envia_un_minuto_antes_del_limite_de_5(self, enviar_mock):
        self.crear_solicitud(minutos_para_empezar=4)
        self.correr_comando()
        enviar_mock.assert_not_called()

    @mock.patch("meetings.management.commands.enviar_recordatorios.enviar_mensaje_telegram")
    def test_no_envia_un_minuto_despues_del_limite_de_5(self, enviar_mock):
        self.crear_solicitud(minutos_para_empezar=6)
        self.correr_comando()
        enviar_mock.assert_not_called()
