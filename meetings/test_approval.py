"""Pruebas de la aprobación en un toque (HU-08): enlace firmado, decisión del ejecutivo y vista de la asistente."""
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.core import signing
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from .links import (
    ExpiredLink, InvalidLink, make_approval_token, make_token, read_approval_token, read_token,
)
from .models import MeetingRequest
from .test_proposal_views import ProposalViewBase

BLOQUES = {f"{d}-10": 1 for d in range(4)}


class ApprovalBase(ProposalViewBase):
    """Solicitud con ambas disponibilidades y propuesta generada (estado propuesta)."""

    def setUp(self):
        super().setUp()
        self.av("ejecutivo", BLOQUES)
        self.av("contraparte", dict(BLOQUES, **{"2-10": 2}))
        self.login(self.asis)
        self.generate()
        self.req.refresh_from_db()
        self.client.logout()

    @property
    def url(self):
        return reverse("public_approval", args=[make_approval_token(self.req.pk)])

    def decide(self, **data):
        return self.client.post(self.url, data)

    def first_slot_id(self):
        html = self.client.get(self.url).content.decode()
        marker = 'name="slot" value="'
        return html.split(marker)[1].split('"')[0]


class ApprovalTokenTests(ApprovalBase):
    def test_el_enlace_de_aprobacion_vuelve_al_mismo_id(self):
        self.assertEqual(read_approval_token(make_approval_token(self.req.pk)), self.req.pk)

    def test_un_enlace_alterado_se_rechaza(self):
        token = make_approval_token(self.req.pk)
        with self.assertRaises(InvalidLink):
            read_approval_token(token[:-2] + ("aa" if not token.endswith("aa") else "bb"))

    @override_settings(APPROVAL_LINK_MAX_AGE=-1)
    def test_un_enlace_vencido_se_rechaza(self):
        with self.assertRaises(ExpiredLink):
            read_approval_token(make_approval_token(self.req.pk))

    def test_el_enlace_de_la_contraparte_no_sirve_para_aprobar_y_viceversa(self):
        with self.assertRaises(InvalidLink):
            read_approval_token(make_token(self.req.pk))
        with self.assertRaises(InvalidLink):
            read_token(make_approval_token(self.req.pk))

    def test_un_token_con_contenido_inesperado_se_rechaza(self):
        token = signing.dumps({"r": "no-es-un-entero"}, salt="quedamos.aprobacion.v1")
        with self.assertRaises(InvalidLink):
            read_approval_token(token)

    def test_el_enlace_de_la_contraparte_no_abre_la_pagina_de_aprobacion(self):
        r = self.client.get(reverse("public_approval", args=[make_token(self.req.pk)]))
        self.assertEqual(r.status_code, 404)


class CreateApprovalLinkTests(ApprovalBase):
    def create(self):
        return self.client.post(reverse("create_approval_link", args=[self.req.pk]))

    def test_la_asistente_genera_el_enlace_sobre_una_propuesta_vigente(self):
        self.login(self.asis)
        r = self.create()
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "/a/")
        self.assertContains(r, "Envíaselo a Carla Ejecutiva")

    def test_el_enlace_generado_abre_la_pagina_publica(self):
        self.login(self.asis)
        url = self.create().content.decode().split('id="enlace-aprobacion"')[0].rsplit('value="', 1)[1].split('"')[0]
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_sin_propuesta_vigente_no_se_genera(self):
        MeetingRequest.objects.filter(pk=self.req.pk).update(status="pendiente")
        self.login(self.asis)
        r = self.client.post(reverse("create_approval_link", args=[self.req.pk]), follow=True)
        self.assertContains(r, "Primero genera una propuesta de horarios")
        self.assertNotContains(r, "/a/")

    def test_una_asistente_sin_vinculo_recibe_404(self):
        self.login(self.otra)
        self.assertEqual(self.create().status_code, 404)

    def test_el_anonimo_es_enviado_a_ingresar(self):
        r = self.create()
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.url.startswith(reverse("login")))

    def test_solo_acepta_post(self):
        self.login(self.asis)
        self.assertEqual(self.client.get(reverse("create_approval_link", args=[self.req.pk])).status_code, 405)

    def test_el_boton_aparece_solo_con_propuesta(self):
        self.login(self.asis)
        self.assertContains(self.detail(), "Generar enlace de aprobación para el ejecutivo")
        MeetingRequest.objects.filter(pk=self.req.pk).update(status="pendiente")
        self.assertNotContains(self.detail(), "Generar enlace de aprobación para el ejecutivo")


class PublicApprovalViewTests(ApprovalBase):
    def test_sin_iniciar_sesion_muestra_las_opciones_con_su_motivo(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Revisión trimestral")
        self.assertContains(r, "Opción 1")
        self.assertContains(r, "Opción 3")
        self.assertContains(r, "Pedro Gómez lo marcó como preferido y Carla Ejecutiva también puede.")
        self.assertContains(r, "Ninguna me sirve")

    def test_cada_opcion_tiene_su_boton_de_aprobar(self):
        self.assertContains(self.client.get(self.url), "Aprobar esta opción", count=3)

    def test_la_pagina_no_se_indexa_ni_filtra_el_referer(self):
        r = self.client.get(self.url)
        self.assertEqual(r["X-Robots-Tag"], "noindex")
        self.assertEqual(r["Referrer-Policy"], "same-origin")

    def test_con_un_toque_la_opcion_queda_aprobada(self):
        slot_id = self.first_slot_id()
        r = self.decide(slot=slot_id)
        self.assertEqual(r.status_code, 302)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "aprobada")
        self.assertIsNotNone(self.req.approved_start)
        self.assertEqual(self.req.approved_end - self.req.approved_start, timedelta(minutes=60))
        self.assertIsNotNone(self.req.decided_at)

    def test_tras_aprobar_el_ejecutivo_ve_la_confirmacion(self):
        self.decide(slot=self.first_slot_id())
        r = self.client.get(self.url)
        self.assertContains(r, "Reunión confirmada")
        self.assertContains(r, "Revisión trimestral")
        self.assertNotContains(r, "Aprobar esta opción")

    def test_la_opcion_aprobada_es_la_elegida(self):
        html = self.client.get(self.url).content.decode()
        ids = [chunk.split('"')[0] for chunk in html.split('name="slot" value="')[1:]]
        self.assertEqual(len(ids), 3)
        elegida = ids[1]
        self.decide(slot=elegida)
        self.req.refresh_from_db()
        dia, hora = (int(x) for x in elegida.split("-"))
        local = self.req.approved_start.astimezone(ZoneInfo("America/Lima"))
        self.assertEqual((local.weekday(), local.hour), (dia, hora))

    def test_un_segundo_toque_no_cambia_lo_ya_aprobado(self):
        html = self.client.get(self.url).content.decode()
        ids = [chunk.split('"')[0] for chunk in html.split('name="slot" value="')[1:]]
        self.decide(slot=ids[0])
        self.req.refresh_from_db()
        primero = (self.req.approved_start, self.req.decided_at)
        self.decide(slot=ids[1])
        self.decide(reject="1")
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "aprobada")
        self.assertEqual((self.req.approved_start, self.req.decided_at), primero)

    def test_la_asistente_ve_reflejada_la_aprobacion(self):
        self.decide(slot=self.first_slot_id())
        self.login(self.asis)
        r = self.detail()
        self.assertContains(r, "Aprobada por el ejecutivo")
        self.assertContains(r, "status aprobada")

    def test_ninguna_me_sirve_pide_otras_opciones(self):
        r = self.decide(reject="1")
        self.assertEqual(r.status_code, 302)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "pendiente")
        self.assertIsNotNone(self.req.new_options_requested_at)
        self.assertIsNone(self.req.approved_start)

    def test_tras_rechazar_el_ejecutivo_ve_el_aviso_y_la_asistente_tambien(self):
        self.decide(reject="1")
        self.assertContains(self.client.get(self.url), "Pedimos otras opciones")
        self.login(self.asis)
        self.assertContains(self.detail(), "El ejecutivo pidió otras opciones")

    def test_al_generar_una_propuesta_nueva_se_limpia_el_pedido(self):
        self.decide(reject="1")
        self.login(self.asis)
        self.generate()
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "propuesta")
        self.assertIsNone(self.req.new_options_requested_at)
        self.assertNotContains(self.detail(), "El ejecutivo pidió otras opciones")

    def test_una_opcion_inexistente_no_aprueba_nada(self):
        r = self.client.post(self.url, {"slot": "9-23"}, follow=True)
        self.assertContains(r, "Esa opción ya no está disponible")
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "propuesta")

    def test_un_toque_sin_decision_no_cambia_nada(self):
        self.decide()
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "propuesta")

    def test_el_enlace_alterado_da_404_y_no_aprueba(self):
        token = make_approval_token(self.req.pk)
        malo = reverse("public_approval", args=[token[:-3] + "xyz"])
        self.assertEqual(self.client.get(malo).status_code, 404)
        self.assertEqual(self.client.post(malo, {"slot": "0-10"}).status_code, 404)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "propuesta")

    @override_settings(APPROVAL_LINK_MAX_AGE=-1)
    def test_el_enlace_vencido_da_410_y_lo_explica(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 410)
        self.assertContains(r, "venció", status_code=410)

    def test_una_solicitud_cancelada_no_se_puede_aprobar(self):
        MeetingRequest.objects.filter(pk=self.req.pk).update(status="cancelada")
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 410)
        self.assertContains(r, "cancelada", status_code=410)
        self.decide(slot="0-10")
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "cancelada")

    def test_una_propuesta_que_ya_no_esta_vigente_se_informa(self):
        MeetingRequest.objects.filter(pk=self.req.pk).update(status="pendiente")
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 410)
        self.assertContains(r, "ya no está vigente", status_code=410)

    def test_una_solicitud_eliminada_da_404(self):
        url = self.url
        self.req.delete()
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_la_pagina_publica_no_muestra_la_disponibilidad_ni_las_notas(self):
        MeetingRequest.objects.filter(pk=self.req.pk).update(notes="Nota interna reservada")
        r = self.client.get(self.url)
        self.assertNotContains(r, "Nota interna reservada")
        self.assertNotContains(r, "ana@x.com")


class ApproveModelTests(ApprovalBase):
    def test_approve_solo_actua_sobre_una_propuesta(self):
        MeetingRequest.objects.filter(pk=self.req.pk).update(status="pendiente")
        self.req.refresh_from_db()
        self.assertFalse(self.req.approve(timezone.now(), timezone.now()))
        self.assertFalse(self.req.request_new_options())
        self.assertFalse(self.req.is_approved)

    def test_is_approved_requiere_estado_y_horario(self):
        self.assertFalse(self.req.is_approved)
        self.assertTrue(self.req.approve(self.req.created_at, self.req.created_at))
        self.assertTrue(self.req.is_approved)
