from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .models import AssistantLink, MeetingRequest

PW = "Secreto-12345"


def mk(email, name, role):
    return User.objects.create_user(username=email, email=email, password=PW, full_name=name, role=role)


class Base(TestCase):
    def setUp(self):
        self.ejec = mk("carla@x.com", "Carla Ejecutiva", "ejecutivo")
        self.ejec2 = mk("luis@x.com", "Luis Ejecutivo", "ejecutivo")
        self.asis = mk("ana@x.com", "Ana Asistente", "asistente")
        self.otra = mk("otra@x.com", "Otra Asistente", "asistente")

    def login(self, user):
        self.client.logout()
        self.assertTrue(self.client.login(username=user.username, password=PW))

    def link(self, code):
        return self.client.post(reverse("link_executive"), {"code": code}, follow=True)

    def new_request(self, executive, **over):
        data = {"executive": executive.pk, "title": "Revisión trimestral", "counterpart_name": "Pedro Gómez",
                "counterpart_email": "", "duration_min": 45, "notes": ""}
        data.update(over)
        return self.client.post(reverse("create_request"), data)


class LinkTests(Base):
    def test_sin_vinculo_la_asistente_no_ve_nada_del_ejecutivo(self):
        MeetingRequest.objects.create(executive=self.ejec, created_by=self.ejec, title="Privada", counterpart_name="X")
        self.login(self.asis)
        r = self.client.get(reverse("panel"))
        self.assertNotContains(r, "Privada")
        self.assertNotContains(r, "Carla Ejecutiva")

    def test_vinculo_con_codigo_en_minusculas_y_con_espacios(self):
        self.login(self.asis)
        r = self.link(f" {self.ejec.link_code.lower()} ")
        self.assertContains(r, "Quedaste vinculada con Carla Ejecutiva")
        self.assertTrue(AssistantLink.objects.filter(assistant=self.asis, executive=self.ejec).exists())

    def test_vincular_dos_veces_no_duplica(self):
        self.login(self.asis)
        self.link(self.ejec.link_code)
        r = self.link(self.ejec.link_code)
        self.assertContains(r, "Ya estabas vinculada")
        self.assertEqual(AssistantLink.objects.count(), 1)

    def test_codigo_invalido(self):
        self.login(self.asis)
        r = self.link("ZZZZZZ")
        self.assertContains(r, "Ese código no existe")
        self.assertEqual(AssistantLink.objects.count(), 0)

    def test_codigo_vacio(self):
        self.login(self.asis)
        r = self.link("   ")
        self.assertContains(r, "Escribe el código")

    def test_un_ejecutivo_no_puede_vincularse(self):
        self.login(self.ejec)
        r = self.client.post(reverse("link_executive"), {"code": self.ejec2.link_code})
        self.assertEqual(r.status_code, 403)

    def test_vinculo_visible_para_ambos_lados(self):
        AssistantLink.objects.create(assistant=self.asis, executive=self.ejec)
        self.login(self.asis)
        self.assertContains(self.client.get(reverse("panel")), "Carla Ejecutiva")
        self.login(self.ejec)
        self.assertContains(self.client.get(reverse("panel")), "Ana Asistente")

    def test_desvincular_quita_el_acceso(self):
        link = AssistantLink.objects.create(assistant=self.asis, executive=self.ejec)
        MeetingRequest.objects.create(executive=self.ejec, created_by=self.ejec, title="Reservada", counterpart_name="X")
        self.login(self.asis)
        self.assertContains(self.client.get(reverse("request_list")), "Reservada")
        self.client.post(reverse("unlink", args=[link.pk]))
        self.assertNotContains(self.client.get(reverse("request_list")), "Reservada")

    def test_un_tercero_no_puede_borrar_un_vinculo_ajeno(self):
        link = AssistantLink.objects.create(assistant=self.asis, executive=self.ejec)
        self.login(self.otra)
        self.assertEqual(self.client.post(reverse("unlink", args=[link.pk])).status_code, 403)
        self.assertTrue(AssistantLink.objects.filter(pk=link.pk).exists())

    def test_no_se_puede_vincular_a_uno_mismo(self):
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError), transaction.atomic():
            AssistantLink.objects.create(assistant=self.ejec, executive=self.ejec)


class RequestTests(Base):
    def setUp(self):
        super().setUp()
        AssistantLink.objects.create(assistant=self.asis, executive=self.ejec)

    def test_la_asistente_vinculada_crea_y_el_ejecutivo_ve(self):
        self.login(self.asis)
        r = self.new_request(self.ejec)
        self.assertRedirects(r, reverse("panel"))
        m = MeetingRequest.objects.get()
        self.assertEqual((m.executive, m.created_by, m.status, m.duration_min), (self.ejec, self.asis, "pendiente", 45))
        self.login(self.ejec)
        self.assertContains(self.client.get(reverse("request_list")), "Revisión trimestral")

    def test_sin_vinculo_no_se_puede_crear_para_ese_ejecutivo(self):
        self.login(self.asis)
        r = self.new_request(self.ejec2)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(MeetingRequest.objects.count(), 0)

    def test_nadie_ve_solicitudes_de_ejecutivos_ajenos(self):
        MeetingRequest.objects.create(executive=self.ejec, created_by=self.asis, title="Solo mía", counterpart_name="X")
        self.login(self.otra)
        self.assertNotContains(self.client.get(reverse("request_list")), "Solo mía")
        self.login(self.ejec2)
        self.assertNotContains(self.client.get(reverse("request_list")), "Solo mía")

    def test_no_se_puede_suplantar_al_creador(self):
        self.login(self.asis)
        self.new_request(self.ejec, created_by=self.otra.pk)
        self.assertEqual(MeetingRequest.objects.get().created_by, self.asis)

    def test_validaciones_de_datos(self):
        self.login(self.asis)
        self.assertEqual(self.new_request(self.ejec, duration_min=33).status_code, 400)
        self.assertEqual(self.new_request(self.ejec, title="a").status_code, 400)
        self.assertEqual(self.new_request(self.ejec, counterpart_name=" ").status_code, 400)
        self.assertEqual(self.new_request(self.ejec, counterpart_email="no-es-correo").status_code, 400)
        self.assertEqual(MeetingRequest.objects.count(), 0)

    def test_el_error_se_muestra_en_pantalla(self):
        self.login(self.asis)
        r = self.new_request(self.ejec, title="a")
        self.assertContains(r, "al menos 3 caracteres", status_code=400)

    def test_anonimo_no_puede_crear_ni_listar(self):
        self.assertEqual(self.client.post(reverse("create_request"), {}).status_code, 302)
        self.assertEqual(self.client.get(reverse("request_list")).status_code, 302)

    def test_crear_exige_post(self):
        self.login(self.asis)
        self.assertEqual(self.client.get(reverse("create_request")).status_code, 405)

    def test_html_del_usuario_se_escapa(self):
        self.login(self.asis)
        self.new_request(self.ejec, title="<script>alert(1)</script>")
        r = self.client.get(reverse("request_list"))
        self.assertNotContains(r, "<script>alert(1)</script>")
        self.assertContains(r, "&lt;script&gt;")


class DemoTests(TestCase):
    def test_demo_de_la_tarjeta_carga_sin_sesion(self):
        r = self.client.get(reverse("demo_card"))
        self.assertContains(r, "Revisión trimestral de ventas")
        self.assertContains(r, "Opción 1")
