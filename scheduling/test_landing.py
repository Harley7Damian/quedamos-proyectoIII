"""Pruebas de la landing publica (TR-44): contenido, planes informativos y redireccion con sesion."""
from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .mock import MOCK_PROPOSAL

PW = "Secreto-12345"


class LandingTests(TestCase):
    def setUp(self):
        self.url = reverse("landing")

    def test_la_raiz_es_la_landing(self):
        self.assertEqual(self.url, "/")

    def test_responde_200_sin_sesion(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "landing.html")

    def test_muestra_la_propuesta_de_valor_y_los_tres_pasos(self):
        r = self.client.get(self.url)
        self.assertContains(r, "Coordina reuniones de ejecutivos sin intercambiar correos")
        self.assertContains(r, "Cómo funciona en tres pasos")
        for paso in ("Se registra la solicitud", "Quedamos propone tres horarios", "El ejecutivo aprueba con un toque"):
            self.assertContains(r, paso)

    def test_muestra_la_demostracion_de_la_tarjeta_con_datos_ficticios(self):
        r = self.client.get(self.url)
        self.assertContains(r, MOCK_PROPOSAL.title)
        for slot in MOCK_PROPOSAL.slots:
            self.assertContains(r, slot.reason)
        self.assertContains(r, "Ejemplo con datos ficticios")
        self.assertContains(r, reverse("demo_card"))

    def test_muestra_los_tres_planes_con_precio_por_definir(self):
        r = self.client.get(self.url)
        for plan in ("Gratis", "Profesional", "Empresa"):
            self.assertContains(r, f'<h3 id="plan-{plan.lower()}">{plan}</h3>', html=True)
        self.assertContains(r, "Por definir", count=3)

    def test_cada_plan_tiene_el_boton_de_acceso_piloto_y_no_hay_cobros(self):
        r = self.client.get(self.url)
        self.assertContains(r, "Solicitar acceso piloto", count=5)  # hero, tres planes y cierre
        self.assertContains(r, "No se realiza ningún cobro")
        self.assertNotContains(r, "<form")
        self.assertNotContains(r, "S/")
        self.assertNotContains(r, "$")

    def test_los_botones_llevan_al_registro_y_hay_enlace_para_ingresar(self):
        r = self.client.get(self.url)
        self.assertContains(r, f'href="{reverse("signup")}"', count=6)  # cabecera + los cinco botones
        self.assertContains(r, f'href="{reverse("login")}"')

    def test_la_marca_lleva_a_la_landing_sin_sesion(self):
        self.assertContains(self.client.get(reverse("login")), 'class="brand" href="/"')

    def test_con_sesion_pasa_directo_al_panel(self):
        User.objects.create_user(username="a@x.com", email="a@x.com", password=PW, full_name="Ana", role="asistente")
        self.client.login(username="a@x.com", password=PW)
        r = self.client.get(self.url)
        self.assertRedirects(r, reverse("panel"), fetch_redirect_response=False)

    def test_solo_acepta_lectura(self):
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_la_demostracion_sigue_disponible(self):
        self.assertEqual(self.client.get(reverse("demo_card")).status_code, 200)
