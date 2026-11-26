"""Pestañas del panel, iconos y avisos con título (rediseño visual de PFCIII2026-117)."""
from django.template import Context, Template
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from accounts.models import Profile, User
from meetings.models import AssistantLink

PW = "Secreto-12345"


class PanelPestanasTests(TestCase):
    def setUp(self):
        self.ejec = User.objects.create_user(username="e@x.com", email="e@x.com", password=PW, full_name="Carla Ejecutiva",
                                             role="ejecutivo")
        self.asis = User.objects.create_user(username="a@x.com", email="a@x.com", password=PW, full_name="Ana Asistente", role="asistente")

    def test_el_panel_ofrece_las_dos_pestanas_con_sus_secciones(self):
        self.client.force_login(self.asis)
        html = self.client.get(reverse("panel")).content.decode()
        self.assertIn('role="tablist"', html)
        for destino in ("solicitudes", "vinculacion"):
            self.assertIn(f'data-destino="{destino}"', html)
            self.assertIn(f'id="{destino}" role="tabpanel"', html)

    def test_sin_vinculos_la_pestana_inicial_es_vinculacion(self):
        for usuario in (self.asis, self.ejec):
            self.client.force_login(usuario)
            self.assertContains(self.client.get(reverse("panel")), 'data-inicial="vinculacion"')

    def test_con_vinculos_la_pestana_inicial_son_las_solicitudes(self):
        AssistantLink.objects.create(assistant=self.asis, executive=self.ejec)
        self.client.force_login(self.asis)
        self.assertContains(self.client.get(reverse("panel")), 'data-inicial="solicitudes"')

    def test_el_estado_de_telegram_y_del_telefono_se_ve_en_insignias(self):
        self.client.force_login(self.asis)
        r = self.client.get(reverse("panel"))
        self.assertContains(r, "Sin vincular")
        self.assertContains(r, "Sin número")
        self.assertContains(r, "Agregar número")
        Profile.objects.update_or_create(user=self.asis, defaults={"telefono": "+51999999999"})
        r = self.client.get(reverse("panel"))
        self.assertContains(r, "Número guardado")
        self.assertContains(r, "Cambiar número")

    def test_el_perfil_agrupa_la_llamada_de_recordatorio(self):
        self.client.force_login(self.asis)
        r = self.client.get(reverse("perfil"))
        self.assertContains(r, "Llamada de recordatorio")
        self.assertContains(r, "Aún no vinculas Telegram")


class IconoYAvisosTests(SimpleTestCase):
    def test_el_icono_se_dibuja_con_el_tamano_pedido_y_oculto_a_lectores(self):
        html = Template('{% include "partials/_icono.html" with n="telefono" s=16 %}').render(Context())
        self.assertIn('width="16"', html)
        self.assertIn('aria-hidden="true"', html)
        self.assertIn("<path", html)

    def test_los_avisos_llevan_titulo_segun_el_tipo(self):
        class Mensaje:
            def __init__(self, nivel, texto):
                self.level_tag = nivel
                self.message = texto

            def __str__(self):
                return self.message
        casos = {"success": "Listo", "error": "No se pudo completar", "warning": "Atención", "info": "Aviso"}
        for nivel, titulo in casos.items():
            with self.subTest(nivel=nivel):
                html = Template('{% include "partials/_avisos.html" %}').render(Context({"messages": [Mensaje(nivel, "Texto de prueba")]}))
                self.assertIn(f'<strong class="aviso-titulo">{titulo}</strong>', html)
                self.assertIn("Texto de prueba", html)
