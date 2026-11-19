"""Pruebas del contenido de los recordatorios de reunión (TR-75)."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.test import TestCase

from meetings.models import MeetingRequest

from .models import User
from .recordatorios import mensaje_recordatorio_5, mensaje_recordatorio_30

LIMA = ZoneInfo("America/Lima")
PW = "Secreto-12345"


def mk(email, name, role):
    return User.objects.create_user(username=email, email=email, password=PW, full_name=name, role=role)


class RecordatoriosTests(TestCase):
    def setUp(self):
        self.ejec = mk("carla@x.com", "Carla Ejecutiva", "ejecutivo")
        self.req = MeetingRequest.objects.create(
            executive=self.ejec,
            created_by=self.ejec,
            title="Revisión de presupuesto",
            counterpart_name="Pedro Gómez",
            duration_min=30,
            week_start=date(2026, 11, 23),
            status=MeetingRequest.Status.APROBADA,
            approved_start=datetime(2026, 11, 23, 15, 0, tzinfo=LIMA),
            approved_end=datetime(2026, 11, 23, 15, 30, tzinfo=LIMA),
        )

    def test_mensaje_30_incluye_contraparte_motivo_y_hora(self):
        texto = mensaje_recordatorio_30(self.req)
        self.assertIn("Pedro Gómez", texto)
        self.assertIn("Revisión de presupuesto", texto)
        self.assertIn("15:00", texto)
        self.assertIn("/visto", texto)

    def test_mensaje_5_incluye_contraparte_motivo_y_hora(self):
        texto = mensaje_recordatorio_5(self.req)
        self.assertIn("Pedro Gómez", texto)
        self.assertIn("Revisión de presupuesto", texto)
        self.assertIn("15:00", texto)
        self.assertIn("/visto", texto)
        self.assertIn("http://localhost:8000/", texto)

    def test_el_mensaje_de_5_minutos_se_distingue_del_de_30(self):
        texto30 = mensaje_recordatorio_30(self.req)
        texto5 = mensaje_recordatorio_5(self.req)
        self.assertNotEqual(texto30, texto5)
        self.assertIn("30 min", texto30)
        self.assertIn("5 min", texto5)

    def test_los_mensajes_son_cortos_para_la_vista_previa(self):
        # La vista previa de notificacion de un celular corta el texto largo;
        # mantenemos los mensajes breves para que se lean completos.
        for texto in (mensaje_recordatorio_30(self.req), mensaje_recordatorio_5(self.req)):
            with self.subTest(texto=texto):
                primera_linea = texto.split("\n")[0]
                self.assertLessEqual(len(primera_linea), 80)
