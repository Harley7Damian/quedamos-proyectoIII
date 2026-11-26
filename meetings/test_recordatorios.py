"""Pruebas del comando que envia los recordatorios de Telegram (TR-76/TR-79)."""
from datetime import date, datetime, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.test import TestCase

from accounts.models import Profile, User

from .models import AvisoEnviado, MeetingRequest

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
        self.assertTrue(AvisoEnviado.objects.filter(solicitud=otra, minutos=30).exists())

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


class CrearReunionPruebaTests(TestCase):
    def setUp(self):
        self.ejec = mk("carla@x.com", "Carla Ejecutiva", "ejecutivo")
        self.asis = mk("ana@x.com", "Ana Asistente", "asistente")

    def test_crea_una_reunion_aprobada_que_empieza_en_los_minutos_pedidos(self):
        from io import StringIO
        out = StringIO()
        call_command("crear_reunion_prueba", "--ejecutivo", "carla@x.com", "--asistente", "ana@x.com", "--en", "12", stdout=out)
        s = MeetingRequest.objects.get()
        self.assertEqual((s.status, s.executive, s.created_by), (MeetingRequest.Status.APROBADA, self.ejec, self.asis))
        from django.utils import timezone
        minutos = (s.approved_start - timezone.now()).total_seconds() / 60
        self.assertTrue(11 <= minutos <= 12.1)
        self.assertEqual(s.approved_end - s.approved_start, timedelta(minutes=30))
        self.assertIn("Empieza a las", out.getvalue())

    def test_sin_asistente_la_crea_el_propio_ejecutivo(self):
        call_command("crear_reunion_prueba", "--ejecutivo", "carla@x.com")
        self.assertEqual(MeetingRequest.objects.get().created_by, self.ejec)

    def test_rechaza_un_correo_inexistente_o_un_rol_equivocado(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command("crear_reunion_prueba", "--ejecutivo", "nadie@x.com")
        with self.assertRaises(CommandError):
            call_command("crear_reunion_prueba", "--ejecutivo", "ana@x.com")


class AntelacionConfigurableTests(TestCase):
    """La antelación es por persona: puede ir de 2 días a 5 minutos antes."""

    def setUp(self):
        self.ejec = mk("carla_ant@x.com", "Carla Antelación", "ejecutivo")
        self.asis = mk("ana_ant@x.com", "Ana Antelación", "asistente")
        self.p_ejec = Profile.objects.create(user=self.ejec, telegram_chat_id="111", telefono="+51999999999")
        self.p_asis = Profile.objects.create(user=self.asis, telegram_chat_id="222")
        self.ahora = datetime(2026, 11, 20, 10, 0, tzinfo=LIMA)

    def crear(self, minutos):
        inicio = self.ahora + timedelta(minutes=minutos)
        return MeetingRequest.objects.create(
            executive=self.ejec, created_by=self.asis, title="Revisión", counterpart_name="Pedro Gómez",
            duration_min=30, week_start=date(2026, 11, 16), status=MeetingRequest.Status.APROBADA,
            approved_start=inicio, approved_end=inicio + timedelta(minutes=30),
        )

    def correr(self, ahora=None):
        patcher = mock.patch("django.utils.timezone.now", return_value=ahora or self.ahora)
        patcher.start()
        self.addCleanup(patcher.stop)
        call_command("enviar_recordatorios")
        patcher.stop()

    @mock.patch("meetings.management.commands.enviar_recordatorios.hacer_llamada_recordatorio")
    @mock.patch("meetings.management.commands.enviar_recordatorios.enviar_mensaje_telegram")
    def test_avisa_dos_dias_antes_solo_a_quien_lo_pidio(self, enviar, llamada):
        self.p_ejec.avisos_minutos = [2880, 30, 5]
        self.p_ejec.save()
        self.crear(2880)
        self.correr()
        self.assertEqual(enviar.call_count, 1)  # la asistente conserva 30 y 5, aún no le toca
        self.assertEqual(enviar.call_args.args[0], "111")
        self.assertIn("En 2 días", enviar.call_args.args[1])
        self.assertIn("a las 10:00", enviar.call_args.args[1])
        llamada.assert_not_called()  # nunca se llama dos días antes

    @mock.patch("meetings.management.commands.enviar_recordatorios.hacer_llamada_recordatorio")
    @mock.patch("meetings.management.commands.enviar_recordatorios.enviar_mensaje_telegram")
    def test_un_dia_antes_dice_manana(self, enviar, llamada):
        self.p_ejec.avisos_minutos = [1440]
        self.p_ejec.save()
        self.crear(1400)
        self.correr()
        self.assertIn("Mañana", enviar.call_args.args[1])

    @mock.patch("meetings.management.commands.enviar_recordatorios.hacer_llamada_recordatorio")
    @mock.patch("meetings.management.commands.enviar_recordatorios.enviar_mensaje_telegram")
    def test_si_llegan_varios_vencidos_envia_solo_el_mas_cercano_y_omite_el_resto(self, enviar, llamada):
        self.p_ejec.avisos_minutos = [1440, 60, 5]
        self.p_ejec.save()
        s = self.crear(20)  # ya vencieron el de 1 día y el de 1 hora; el de 5 min aún no
        self.correr()
        textos_ejec = [c.args[1] for c in enviar.call_args_list if c.args[0] == "111"]
        self.assertEqual(len(textos_ejec), 1)
        self.assertIn("En 1 hora", textos_ejec[0])
        registros = {a.minutos: a.omitido for a in AvisoEnviado.objects.filter(solicitud=s, usuario=self.ejec)}
        self.assertEqual(registros, {1440: True, 60: False})

    @mock.patch("meetings.management.commands.enviar_recordatorios.hacer_llamada_recordatorio")
    @mock.patch("meetings.management.commands.enviar_recordatorios.enviar_mensaje_telegram")
    def test_cada_aviso_llega_una_sola_vez_aunque_el_comando_corra_muchas(self, enviar, llamada):
        self.p_ejec.avisos_minutos = [60, 5]
        self.p_ejec.save()
        self.crear(60)
        self.correr()
        self.correr()
        self.correr(self.ahora + timedelta(minutes=30))
        textos = [c.args[1] for c in enviar.call_args_list if c.args[0] == "111"]
        self.assertEqual(len(textos), 1)
        self.correr(self.ahora + timedelta(minutes=56))
        textos = [c.args[1] for c in enviar.call_args_list if c.args[0] == "111"]
        self.assertEqual(len(textos), 2)
        self.assertIn("En 5 min", textos[1])

    @mock.patch("meetings.management.commands.enviar_recordatorios.hacer_llamada_recordatorio")
    @mock.patch("meetings.management.commands.enviar_recordatorios.enviar_mensaje_telegram")
    def test_la_llamada_va_en_el_ultimo_aviso_si_es_de_15_minutos_o_menos(self, enviar, llamada):
        self.p_ejec.avisos_minutos = [60, 15]
        self.p_ejec.save()
        self.crear(60)
        self.correr()
        llamada.assert_not_called()  # el de 60 no es el último
        self.correr(self.ahora + timedelta(minutes=46))
        llamada.assert_called_once()
        texto = llamada.call_args.args[1]
        self.assertNotIn("http", texto)
        self.assertNotIn("/visto", texto)
        self.assertIn("Pedro Gómez", texto)

    @mock.patch("meetings.management.commands.enviar_recordatorios.hacer_llamada_recordatorio")
    @mock.patch("meetings.management.commands.enviar_recordatorios.enviar_mensaje_telegram")
    def test_si_el_ultimo_aviso_es_de_una_hora_no_se_llama(self, enviar, llamada):
        self.p_ejec.avisos_minutos = [60]
        self.p_ejec.save()
        self.crear(55)
        self.correr()
        enviar.assert_called()
        llamada.assert_not_called()

    def test_las_preferencias_invalidas_vuelven_a_los_valores_de_siempre(self):
        self.p_ejec.avisos_minutos = [7, "x", None]
        self.assertEqual(self.p_ejec.avisos_efectivos, [30, 5])
        self.p_ejec.avisos_minutos = [5, 1440, 1440, 30]
        self.assertEqual(self.p_ejec.avisos_efectivos, [1440, 30, 5])
