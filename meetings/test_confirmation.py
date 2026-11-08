"""Pruebas de la confirmación (HU-09): archivo .ics de la reunión aprobada y historial de reuniones confirmadas."""
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.urls import reverse

from .ics import build_ics, escape_text, fold_line
from .links import make_approval_token, make_token
from .models import MeetingRequest
from .test_approval import ApprovalBase

LIMA = ZoneInfo("America/Lima")


def unfold(text):
    """Deshace el plegado de lineas para poder leer el contenido como lo haria un calendario."""
    return text.replace("\r\n ", "")


class ConfirmBase(ApprovalBase):
    def approve(self):
        url = reverse("public_approval", args=[make_approval_token(self.req.pk)])
        html = self.client.get(url).content.decode()
        slot_id = html.split('name="slot" value="')[1].split('"')[0]
        self.client.post(url, {"slot": slot_id})
        self.req.refresh_from_db()
        return self.req


class IcsContentTests(ConfirmBase):
    def test_una_reunion_sin_aprobar_no_genera_archivo(self):
        with self.assertRaises(ValueError):
            build_ics(self.req)

    def test_estructura_basica_de_la_invitacion(self):
        ics = build_ics(self.approve())
        self.assertTrue(ics.startswith("BEGIN:VCALENDAR\r\n"))
        self.assertTrue(ics.endswith("END:VCALENDAR\r\n"))
        for linea in ("VERSION:2.0", "BEGIN:VEVENT", "END:VEVENT", "STATUS:CONFIRMED", f"UID:quedamos-{self.req.pk}@quedamos"):
            self.assertIn(linea + "\r\n", ics)
        self.assertNotIn("\n", ics.replace("\r\n", ""))

    def test_las_horas_se_guardan_en_utc_y_corresponden_a_lo_aprobado(self):
        req = self.approve()
        ics = build_ics(req)
        inicio = req.approved_start.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        fin = req.approved_end.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.assertIn(f"DTSTART:{inicio}\r\n", ics)
        self.assertIn(f"DTEND:{fin}\r\n", ics)
        local = req.approved_start.astimezone(LIMA)
        utc = datetime.strptime(inicio, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt_timezone.utc)
        self.assertEqual(utc.astimezone(LIMA), local)
        self.assertEqual(req.approved_end - req.approved_start, timedelta(minutes=60))

    def test_el_resumen_incluye_asunto_y_contraparte(self):
        ics = unfold(build_ics(self.approve()))
        self.assertIn("SUMMARY:Revisión trimestral con Pedro Gómez\r\n", ics)

    def test_no_filtra_notas_ni_correos(self):
        MeetingRequest.objects.filter(pk=self.req.pk).update(notes="Nota privada de la asistente", counterpart_email="pedro@cliente.com")
        ics = build_ics(self.approve())
        self.assertNotIn("Nota privada", ics)
        self.assertNotIn("pedro@cliente.com", ics)

    def test_el_mismo_archivo_se_genera_igual_dos_veces(self):
        req = self.approve()
        self.assertEqual(build_ics(req), build_ics(req))

    def test_escape_de_caracteres_especiales(self):
        self.assertEqual(escape_text("a,b;c\\d\ne"), "a\\,b\\;c\\\\d\\ne")

    def test_un_asunto_con_caracteres_especiales_no_rompe_el_archivo(self):
        MeetingRequest.objects.filter(pk=self.req.pk).update(title="Cierre; contrato, fase 2")
        req = self.approve()
        ics = unfold(build_ics(req))
        self.assertIn("SUMMARY:Cierre\\; contrato\\, fase 2 con Pedro Gómez\r\n", ics)

    def test_las_lineas_largas_se_pliegan_a_75_octetos(self):
        largo = "ñ" * 120
        for linea in fold_line("SUMMARY:" + largo).split("\r\n"):
            self.assertLessEqual(len(linea.encode("utf-8")), 75)
        self.assertEqual(unfold(fold_line("SUMMARY:" + largo)), "SUMMARY:" + largo)


class AssistantDownloadTests(ConfirmBase):
    def url(self):
        return reverse("request_ics", args=[self.req.pk])

    def test_la_asistente_descarga_la_invitacion_tras_la_aprobacion(self):
        self.approve()
        self.login(self.asis)
        r = self.client.get(self.url())
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r["Content-Type"].startswith("text/calendar"))
        self.assertIn(f'filename="reunion-{self.req.pk}.ics"', r["Content-Disposition"])
        self.assertIn("BEGIN:VEVENT", r.content.decode())

    def test_el_ejecutivo_tambien_puede_descargarla_con_su_sesion(self):
        self.approve()
        self.login(self.ejec)
        self.assertEqual(self.client.get(self.url()).status_code, 200)

    def test_antes_de_la_aprobacion_da_404(self):
        self.login(self.asis)
        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_una_asistente_sin_vinculo_recibe_404(self):
        self.approve()
        self.login(self.otra)
        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_el_anonimo_es_enviado_a_ingresar(self):
        self.approve()
        r = self.client.get(self.url())
        self.assertEqual(r.status_code, 302)
        self.assertIn("/acceso/", r["Location"])

    def test_el_detalle_muestra_el_enlace_de_descarga_solo_si_esta_aprobada(self):
        self.login(self.asis)
        self.assertNotContains(self.detail(), "Descargar invitación")
        self.approve()
        self.login(self.asis)
        self.assertContains(self.detail(), self.url())


class ExecutiveDownloadTests(ConfirmBase):
    def ics_url(self, token=None):
        return reverse("approval_ics", args=[token or make_approval_token(self.req.pk)])

    def test_el_ejecutivo_descarga_desde_su_enlace_sin_iniciar_sesion(self):
        self.approve()
        r = self.client.get(self.ics_url())
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r["Content-Type"].startswith("text/calendar"))
        self.assertEqual(r["X-Robots-Tag"], "noindex")

    def test_la_pagina_de_confirmacion_ofrece_la_descarga(self):
        self.approve()
        page = self.client.get(reverse("public_approval", args=[make_approval_token(self.req.pk)]))
        self.assertContains(page, "Añadir a mi calendario")
        self.assertContains(page, self.ics_url())

    def test_antes_de_aprobar_no_hay_archivo(self):
        self.assertEqual(self.client.get(self.ics_url()).status_code, 404)

    def test_el_enlace_de_la_contraparte_no_sirve_para_descargar(self):
        self.approve()
        self.assertEqual(self.client.get(self.ics_url(make_token(self.req.pk))).status_code, 404)

    def test_un_enlace_alterado_da_404(self):
        self.approve()
        self.assertEqual(self.client.get(self.ics_url(make_approval_token(self.req.pk) + "x")).status_code, 404)


class HistoryTests(ConfirmBase):
    def test_la_reunion_confirmada_aparece_en_el_historial(self):
        self.approve()
        self.login(self.asis)
        r = self.client.get(reverse("history"))
        self.assertContains(r, "Revisión trimestral")
        self.assertContains(r, "Pedro Gómez")
        self.assertContains(r, reverse("request_ics", args=[self.req.pk]))

    def test_una_reunion_sin_aprobar_no_aparece(self):
        self.login(self.asis)
        r = self.client.get(reverse("history"))
        self.assertNotContains(r, "Revisión trimestral")
        self.assertContains(r, "Aún no hay reuniones confirmadas")

    def test_el_ejecutivo_ve_las_suyas(self):
        self.approve()
        self.login(self.ejec)
        self.assertContains(self.client.get(reverse("history")), "Revisión trimestral")

    def test_una_asistente_sin_vinculo_no_ve_reuniones_ajenas(self):
        self.approve()
        self.login(self.otra)
        self.assertNotContains(self.client.get(reverse("history")), "Revisión trimestral")

    def test_el_anonimo_es_enviado_a_ingresar(self):
        self.assertEqual(self.client.get(reverse("history")).status_code, 302)

    def test_la_barra_lateral_enlaza_al_historial(self):
        self.login(self.asis)
        self.assertContains(self.client.get(reverse("panel")), reverse("history"))
