"""Pruebas de las vistas separadas por rol (TR-48): la asistente coordina y el ejecutivo sigue y aprueba."""
from django.urls import reverse

from .links import make_approval_token
from .models import Availability, MeetingRequest
from .test_approval import ApprovalBase

ACCIONES_DE_LA_ASISTENTE = (
    "Guardar disponibilidad del ejecutivo",
    "Importar desde un calendario (.ics)",
    "Generar enlace para la contraparte",
    "Generar enlace de aprobación para el ejecutivo",
    "Volver a generar la propuesta",
)


class VistaDeLaAsistenteTests(ApprovalBase):
    def detalle(self):
        self.login(self.asis)
        return self.client.get(reverse("request_detail", args=[self.req.pk]))

    def test_muestra_todas_las_acciones_de_coordinacion(self):
        r = self.detalle()
        for accion in ACCIONES_DE_LA_ASISTENTE:
            self.assertContains(r, accion)

    def test_se_identifica_como_vista_de_asistente(self):
        r = self.detalle()
        self.assertContains(r, "Vista de asistente")
        self.assertNotContains(r, "Vista de ejecutivo")

    def test_la_lista_ofrece_ver_detalle_y_coordinar(self):
        self.login(self.asis)
        self.assertContains(self.client.get(reverse("request_list")), "Ver detalle y coordinar")

    def test_el_panel_ofrece_crear_solicitudes_y_vincularse(self):
        self.login(self.asis)
        r = self.client.get(reverse("panel"))
        self.assertContains(r, 'id="nueva-solicitud"')
        self.assertContains(r, "Vincularme con un ejecutivo")

    def test_ve_que_el_ejecutivo_pidio_otras_opciones(self):
        self.req.request_new_options()
        self.assertContains(self.detalle(), "El ejecutivo pidió otras opciones")

    def test_puede_generar_el_enlace_de_aprobacion(self):
        self.login(self.asis)
        r = self.client.post(reverse("create_approval_link", args=[self.req.pk]), follow=True)
        self.assertContains(r, "enlace-aprobacion")


class VistaDelEjecutivoTests(ApprovalBase):
    def detalle(self):
        self.login(self.ejec)
        return self.client.get(reverse("request_detail", args=[self.req.pk]))

    def test_no_muestra_ninguna_accion_de_coordinacion(self):
        r = self.detalle()
        self.assertEqual(r.status_code, 200)
        for accion in ACCIONES_DE_LA_ASISTENTE:
            self.assertNotContains(r, accion)
        for url in ("save_executive_availability", "import_executive_calendar", "create_counterpart_link",
                    "create_approval_link", "generate_proposal"):
            self.assertNotContains(r, reverse(url, args=[self.req.pk]))

    def test_se_identifica_como_vista_de_ejecutivo(self):
        r = self.detalle()
        self.assertContains(r, "Vista de ejecutivo")
        self.assertNotContains(r, "Vista de asistente")

    def test_ve_el_estado_y_las_opciones_propuestas_sin_poder_generarlas(self):
        r = self.detalle()
        self.assertContains(r, "Opción 1")
        self.assertContains(r, "Tu asistente te enviará el enlace")

    def test_ve_que_su_asistente_registro_la_disponibilidad(self):
        self.assertContains(self.detalle(), "Tu asistente registró tu disponibilidad")

    def test_sin_propuesta_ve_que_su_asistente_coordina(self):
        otra = MeetingRequest.objects.create(
            executive=self.ejec, created_by=self.asis, title="Sin propuesta", counterpart_name="Z", week_start=self.req.week_start,
        )
        self.login(self.ejec)
        r = self.client.get(reverse("request_detail", args=[otra.pk]))
        self.assertContains(r, "Tu asistente coordina esta reunión")
        self.assertContains(r, "Tu asistente aún no registra tu disponibilidad")

    def test_ve_que_pidio_otras_opciones(self):
        self.req.request_new_options()
        r = self.detalle()
        self.assertContains(r, "Pediste otras opciones")
        self.assertNotContains(r, "El ejecutivo pidió otras opciones")

    def test_la_lista_ofrece_solo_ver_el_detalle(self):
        self.login(self.ejec)
        r = self.client.get(reverse("request_list"))
        self.assertContains(r, "Ver detalle")
        self.assertNotContains(r, "Ver detalle y coordinar")

    def test_el_panel_no_ofrece_crear_solicitudes_ni_vincularse(self):
        self.login(self.ejec)
        r = self.client.get(reverse("panel"))
        self.assertNotContains(r, 'id="nueva-solicitud"')
        self.assertNotContains(r, "Vincularme con un ejecutivo")
        self.assertContains(r, self.ejec.link_code)

    def test_aprobada_ve_la_reunion_y_puede_descargar_la_invitacion(self):
        url = reverse("public_approval", args=[make_approval_token(self.req.pk)])
        html = self.client.get(url).content.decode()
        self.client.post(url, {"slot": html.split('name="slot" value="')[1].split('"')[0]})
        r = self.detalle()
        self.assertContains(r, "Aprobada por el ejecutivo")
        self.assertContains(r, reverse("request_ics", args=[self.req.pk]))

    def test_conserva_el_acceso_a_las_reglas_el_historial_y_las_metricas(self):
        self.login(self.ejec)
        for nombre in ("rules", "history", "metrics"):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 200)


class AccionesDeCoordinacionSoloDeLaAsistenteTests(ApprovalBase):
    def post(self, nombre, usuario, *args, **datos):
        self.login(usuario)
        return self.client.post(reverse(nombre, args=args), datos)

    def test_el_ejecutivo_recibe_403_en_cada_accion_de_coordinacion(self):
        pk = self.req.pk
        for nombre in ("save_executive_availability", "import_executive_calendar", "create_counterpart_link",
                       "create_approval_link", "generate_proposal"):
            with self.subTest(accion=nombre):
                self.assertEqual(self.post(nombre, self.ejec, pk, **{"b-0-9": "1"}).status_code, 403)

    def test_el_ejecutivo_no_puede_crear_solicitudes(self):
        antes = MeetingRequest.objects.count()
        r = self.post("create_request", self.ejec, title="X", counterpart_name="Y", executive=self.ejec.pk, duration_min=30)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(MeetingRequest.objects.count(), antes)

    def test_lo_que_intenta_el_ejecutivo_no_cambia_nada(self):
        antes = Availability.objects.get(request=self.req, party="ejecutivo").blocks
        self.post("save_executive_availability", self.ejec, self.req.pk, **{"b-6-20": "1"})
        self.assertEqual(Availability.objects.get(request=self.req, party="ejecutivo").blocks, antes)
        enlaces = MeetingRequest.objects.get(pk=self.req.pk).links_shared
        self.post("create_counterpart_link", self.ejec, self.req.pk)
        self.assertEqual(MeetingRequest.objects.get(pk=self.req.pk).links_shared, enlaces)

    def test_sin_iniciar_sesion_sigue_redirigiendo_al_acceso(self):
        self.client.logout()
        r = self.client.post(reverse("generate_proposal", args=[self.req.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/acceso/", r["Location"])

    def test_la_asistente_conserva_todas_las_acciones(self):
        pk = self.req.pk
        self.assertEqual(self.post("create_approval_link", self.asis, pk).status_code, 200)
        self.assertEqual(self.post("create_counterpart_link", self.asis, pk).status_code, 200)
        self.assertEqual(self.post("generate_proposal", self.asis, pk).status_code, 302)
        self.assertEqual(self.post("save_executive_availability", self.asis, pk, **{"b-0-9": "1"}).status_code, 302)
