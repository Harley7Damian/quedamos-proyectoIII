"""Pulido del panel: saludo, resumen por estado, tarjetas clicables y boton para volver."""
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from meetings.models import AssistantLink, MeetingRequest
from scheduling.templatetags.scheduling_extras import primer_nombre


class PanelPulidoTests(TestCase):
    def setUp(self):
        self.ejec = User.objects.create_user(username="e@x.com", email="e@x.com", password="Secreto-12345", full_name="Carla Ejecutiva", role="ejecutivo")
        self.asis = User.objects.create_user(username="a@x.com", email="a@x.com", password="Secreto-12345", full_name="Ana Asistente", role="asistente")
        AssistantLink.objects.create(assistant=self.asis, executive=self.ejec)
        for estado in ("pendiente", "pendiente", "propuesta", "aprobada"):
            self.req = MeetingRequest.objects.create(
                executive=self.ejec, created_by=self.asis, title="Reunión", counterpart_name="Pedro", status=estado
            )
        self.client.force_login(self.asis)

    def test_el_filtro_devuelve_solo_el_primer_nombre(self):
        self.assertEqual(primer_nombre("Ana María Torres"), "Ana")
        self.assertEqual(primer_nombre(""), "")
        self.assertEqual(primer_nombre(None), "")

    def test_el_panel_saluda_por_el_primer_nombre(self):
        self.assertContains(self.client.get(reverse("panel")), "Hola, Ana")

    def test_el_resumen_cuenta_las_solicitudes_por_estado(self):
        r = self.client.get(reverse("request_list"))
        self.assertEqual(r.context["resumen"], {"total": 4, "por_coordinar": 2, "propuestas": 1, "confirmadas": 1})
        self.assertContains(r, "Por coordinar")
        self.assertContains(r, "Esperando aprobación")
        self.assertContains(r, "Confirmadas")

    def test_sin_solicitudes_no_se_muestra_el_resumen(self):
        MeetingRequest.objects.all().delete()
        self.assertNotContains(self.client.get(reverse("request_list")), 'class="resumen"')

    def test_el_titulo_de_cada_tarjeta_es_un_enlace_al_detalle(self):
        r = self.client.get(reverse("request_list"))
        self.assertContains(r, f'class="enlace-tarjeta" href="{reverse("request_detail", args=[self.req.pk])}"')

    def test_el_detalle_tiene_un_boton_volver_con_icono(self):
        r = self.client.get(reverse("request_detail", args=[self.req.pk]))
        self.assertContains(r, 'class="boton-volver"')
        self.assertContains(r, "Volver a las solicitudes")

    def test_la_accion_de_cada_tarjeta_es_un_enlace_real_al_detalle(self):
        r = self.client.get(reverse("request_list"))
        self.assertContains(r, f'<a class="accion-flecha" href="{reverse("request_detail", args=[self.req.pk])}">')
        self.assertNotContains(r, '<span class="accion-flecha"')
