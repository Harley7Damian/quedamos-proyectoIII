"""Pruebas de la coordinacion con la contraparte (HU-05): enlace firmado, privacidad y disponibilidad."""
from datetime import date

from django.core import signing
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

from .links import SALT, make_token, read_token
from .models import AssistantLink, Availability, MeetingRequest
from .weeks import default_week_start, monday_of

PW = "Secreto-12345"


def mk(email, name, role):
    return User.objects.create_user(username=email, email=email, password=PW, full_name=name, role=role)


class CoordinationBase(TestCase):
    def setUp(self):
        self.ejec = mk("carla@x.com", "Carla Ejecutiva", "ejecutivo")
        self.asis = mk("ana@x.com", "Ana Asistente", "asistente")
        self.otra = mk("otra@x.com", "Otra Asistente", "asistente")
        AssistantLink.objects.create(assistant=self.asis, executive=self.ejec)
        self.req = MeetingRequest.objects.create(
            executive=self.ejec, created_by=self.asis, title="Revisión trimestral", counterpart_name="Pedro Gómez",
            counterpart_email="pedro@otra.com", duration_min=60, notes="Nota interna reservada",
            week_start=date(2026, 10, 26),
        )

    def login(self, user):
        self.client.logout()
        self.assertTrue(self.client.login(username=user.username, password=PW))

    def public_url(self, request_id=None):
        return reverse("public_availability", args=[make_token(request_id or self.req.pk)])


class TokenTests(CoordinationBase):
    def test_el_token_devuelve_el_id_de_la_solicitud(self):
        self.assertEqual(read_token(make_token(self.req.pk)), self.req.pk)

    def test_un_token_alterado_es_invalido(self):
        token = make_token(self.req.pk)
        self.client.logout()
        response = self.client.get(reverse("public_availability", args=[token[:-2] + "xx"]))
        self.assertEqual(response.status_code, 404)

    def test_un_token_de_otra_sal_no_sirve(self):
        forged = signing.dumps({"r": self.req.pk}, salt="otra.sal")
        response = self.client.get(reverse("public_availability", args=[forged]))
        self.assertEqual(response.status_code, 404)

    def test_un_token_con_contenido_distinto_a_un_id_es_invalido(self):
        forged = signing.dumps({"r": "abc"}, salt=SALT)
        response = self.client.get(reverse("public_availability", args=[forged]))
        self.assertEqual(response.status_code, 404)

    @override_settings(COUNTERPART_LINK_MAX_AGE=-1)
    def test_un_enlace_vencido_responde_410(self):
        response = self.client.get(self.public_url())
        self.assertEqual(response.status_code, 410)
        self.assertContains(response, "venció", status_code=410)

    def test_un_token_de_una_solicitud_inexistente_es_404(self):
        response = self.client.get(self.public_url(request_id=99999))
        self.assertEqual(response.status_code, 404)


class DetailAndLinkTests(CoordinationBase):
    def test_la_asistente_vinculada_ve_el_detalle_y_genera_el_enlace(self):
        self.login(self.asis)
        self.assertContains(self.client.get(reverse("request_detail", args=[self.req.pk])), "Revisión trimestral")
        response = self.client.post(reverse("create_counterpart_link", args=[self.req.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/c/")
        self.assertContains(response, "solo da acceso a esta solicitud")

    def test_el_ejecutivo_dueno_tambien_puede_ver_el_detalle(self):
        self.login(self.ejec)
        self.assertEqual(self.client.get(reverse("request_detail", args=[self.req.pk])).status_code, 200)

    def test_una_asistente_sin_vinculo_recibe_404_en_detalle_y_enlace(self):
        self.login(self.otra)
        self.assertEqual(self.client.get(reverse("request_detail", args=[self.req.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("create_counterpart_link", args=[self.req.pk])).status_code, 404)

    def test_al_desvincular_se_pierde_el_acceso_al_detalle(self):
        AssistantLink.objects.all().delete()
        self.login(self.asis)
        self.assertEqual(self.client.get(reverse("request_detail", args=[self.req.pk])).status_code, 404)

    def test_el_anonimo_es_enviado_al_ingreso(self):
        response = self.client.get(reverse("request_detail", args=[self.req.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/acceso/", response["Location"])
        self.assertEqual(self.client.post(reverse("create_counterpart_link", args=[self.req.pk])).status_code, 302)

    def test_generar_el_enlace_exige_post(self):
        self.login(self.asis)
        self.assertEqual(self.client.get(reverse("create_counterpart_link", args=[self.req.pk])).status_code, 405)

    def test_una_solicitud_cancelada_no_genera_enlace(self):
        self.req.status = MeetingRequest.Status.CANCELADA
        self.req.save()
        self.login(self.asis)
        response = self.client.post(reverse("create_counterpart_link", args=[self.req.pk]), follow=True)
        self.assertContains(response, "ya no recibe disponibilidad")


class PublicPageTests(CoordinationBase):
    def test_se_abre_sin_cuenta_y_solo_muestra_el_asunto_y_la_duracion(self):
        self.client.logout()
        response = self.client.get(self.public_url())
        self.assertContains(response, "Revisión trimestral")
        self.assertContains(response, "60 min")
        for secreto in ("Carla Ejecutiva", "carla@x.com", "Nota interna reservada", "pedro@otra.com", "Ana Asistente"):
            self.assertNotContains(response, secreto)

    def test_la_pagina_publica_no_filtra_el_enlace_ni_se_indexa(self):
        response = self.client.get(self.public_url())
        self.assertEqual(response["Referrer-Policy"], "same-origin")
        self.assertEqual(response["X-Robots-Tag"], "noindex")

    def test_la_contraparte_guarda_su_disponibilidad(self):
        response = self.client.post(self.public_url(), {"b-0-9": "1", "b-0-10": "2", "b-2-15": "1"})
        self.assertEqual(response.status_code, 302)
        saved = Availability.objects.get(request=self.req, party=Availability.Party.CONTRAPARTE)
        self.assertEqual(saved.blocks, {"0-9": 1, "0-10": 2, "2-15": 1})

    def test_reenviar_reemplaza_y_no_duplica(self):
        self.client.post(self.public_url(), {"b-0-9": "1"})
        self.client.post(self.public_url(), {"b-3-11": "2"})
        self.assertEqual(Availability.objects.filter(request=self.req).count(), 1)
        self.assertEqual(Availability.objects.get(request=self.req).blocks, {"3-11": 2})

    def test_valores_invalidos_se_ignoran(self):
        response = self.client.post(self.public_url(), {
            "b-0-9": "1", "b-9-9": "1", "b-0-3": "1", "b-0-10": "7", "b-1-10": "x", "otro": "1", "b-0-99": "1"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Availability.objects.get(request=self.req).blocks, {"0-9": 1})

    def test_sin_ningun_horario_marcado_muestra_error_y_no_guarda(self):
        response = self.client.post(self.public_url(), {"b-0-9": "0"})
        self.assertContains(response, "Marca al menos un horario", status_code=400)
        self.assertFalse(Availability.objects.exists())

    def test_el_enlace_de_una_solicitud_no_escribe_en_otra(self):
        otra = MeetingRequest.objects.create(executive=self.ejec, created_by=self.ejec, title="Otra", counterpart_name="Z")
        self.client.post(self.public_url(), {"b-0-9": "1"})
        self.assertFalse(Availability.objects.filter(request=otra).exists())

    def test_una_solicitud_aprobada_o_cancelada_cierra_el_enlace(self):
        for estado in (MeetingRequest.Status.APROBADA, MeetingRequest.Status.CANCELADA):
            self.req.status = estado
            self.req.save()
            self.assertEqual(self.client.get(self.public_url()).status_code, 410)
            self.assertEqual(self.client.post(self.public_url(), {"b-0-9": "1"}).status_code, 410)
        self.assertFalse(Availability.objects.exists())

    def test_al_volver_a_abrir_se_ven_los_horarios_ya_marcados(self):
        self.client.post(self.public_url(), {"b-1-9": "2"})
        response = self.client.get(self.public_url())
        self.assertContains(response, 'name="b-1-9" value="2"')
        self.assertContains(response, "Ya registraste tu disponibilidad")

    def test_el_detalle_refleja_que_la_contraparte_respondio(self):
        self.login(self.asis)
        self.assertContains(self.client.get(reverse("request_detail", args=[self.req.pk])), "Aún no responde")
        self.client.logout()
        self.client.post(self.public_url(), {"b-1-9": "2", "b-1-10": "1"})
        self.login(self.asis)
        self.assertContains(self.client.get(reverse("request_detail", args=[self.req.pk])), "2 horarios marcados")


class WeekTests(CoordinationBase):
    def test_monday_of(self):
        self.assertEqual(monday_of(date(2026, 10, 28)), date(2026, 10, 26))
        self.assertEqual(monday_of(date(2026, 11, 1)), date(2026, 10, 26))

    def test_semana_por_defecto_entre_semana_y_fin_de_semana(self):
        self.assertEqual(default_week_start(date(2026, 10, 28)), date(2026, 10, 26))
        self.assertEqual(default_week_start(date(2026, 10, 31)), date(2026, 11, 2))
        self.assertEqual(default_week_start(date(2026, 11, 1)), date(2026, 11, 2))

    def test_el_formulario_guarda_la_semana_elegida(self):
        self.login(self.asis)
        this_monday = monday_of(timezone.localdate())
        self.client.post(reverse("create_request"), {
            "executive": self.ejec.pk, "title": "Con semana", "counterpart_name": "Pedro", "counterpart_email": "",
            "duration_min": 30, "notes": "", "week": this_monday.isoformat()})
        self.assertEqual(MeetingRequest.objects.get(title="Con semana").week_start, this_monday)

    def test_sin_elegir_semana_se_usa_la_semana_por_defecto(self):
        self.login(self.asis)
        self.client.post(reverse("create_request"), {
            "executive": self.ejec.pk, "title": "Sin semana", "counterpart_name": "Pedro", "counterpart_email": "",
            "duration_min": 30, "notes": ""})
        self.assertIsNotNone(MeetingRequest.objects.get(title="Sin semana").week_start)

    def test_una_semana_que_no_es_opcion_es_rechazada(self):
        self.login(self.asis)
        response = self.client.post(reverse("create_request"), {
            "executive": self.ejec.pk, "title": "Mala semana", "counterpart_name": "Pedro", "counterpart_email": "",
            "duration_min": 30, "notes": "", "week": "2020-01-06"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(MeetingRequest.objects.filter(title="Mala semana").exists())

    def test_sin_semana_guardada_se_usa_la_de_creacion(self):
        sin = MeetingRequest.objects.create(executive=self.ejec, created_by=self.ejec, title="Vieja", counterpart_name="Z")
        self.assertEqual(sin.effective_week_start.weekday(), 0)
