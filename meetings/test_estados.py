"""Pruebas de los estados visibles (TR-58): color, icono y texto en la lista y el detalle."""
from django.urls import reverse

from .test_approval import ApprovalBase


class EstadosVisiblesTests(ApprovalBase):
    """TR-58: cada estado se ve con color, icono y texto; la reunion confirmada se destaca."""

    def lista(self, usuario=None):
        self.login(usuario or self.asis)
        return self.client.get(reverse("request_list"))

    def test_propuesta_lista_muestra_etiqueta_color_e_icono(self):
        r = self.lista()
        self.assertContains(r, "Propuesta lista")
        self.assertContains(r, "estado-propuesta")
        self.assertContains(r, 'class="estado-icono"')
        self.assertContains(r, "Ver detalle y coordinar")

    def test_pendiente_sin_respuesta_de_la_contraparte(self):
        self.req.availabilities.filter(party="contraparte").delete()
        self.req.status = "pendiente"
        self.req.save(update_fields=["status"])
        r = self.lista()
        self.assertContains(r, "estado-pendiente")
        self.assertNotContains(r, "Contraparte respondió")

    def test_pendiente_con_respuesta_de_la_contraparte_dice_que_respondio(self):
        self.req.status = "pendiente"
        self.req.save(update_fields=["status"])
        r = self.lista()
        self.assertContains(r, "Contraparte respondió")
        self.assertContains(r, "estado-respondio")

    def test_pidio_otras_opciones_se_distingue(self):
        self.req.request_new_options()
        self.assertContains(self.lista(), "estado-otras")

    def test_aprobada_destaca_el_horario_y_ofrece_ver_resultado_como_boton(self):
        self.decide(slot=self.first_slot_id())
        r = self.lista()
        self.assertContains(r, "estado-aprobada")
        self.assertContains(r, "card-confirmada")
        self.assertContains(r, "confirmada-horario")
        self.assertContains(r, 'class="btn" href="' + reverse("request_detail", args=[self.req.pk]) + '">Ver resultado')
        self.assertNotContains(r, "Ver detalle y coordinar")

    def test_el_ejecutivo_tambien_ve_ver_resultado_si_esta_aprobada(self):
        self.decide(slot=self.first_slot_id())
        self.assertContains(self.lista(self.ejec), "Ver resultado")

    def test_el_detalle_destaca_la_confirmacion_sin_perder_el_texto_ni_la_clase(self):
        self.decide(slot=self.first_slot_id())
        self.login(self.asis)
        r = self.detail()
        self.assertContains(r, 'class="confirmacion"')
        self.assertContains(r, "Aprobada por el ejecutivo")
        self.assertContains(r, "status aprobada")
        self.assertContains(r, "Descargar invitación (.ics)")

    def test_cancelada_tiene_su_propio_estado(self):
        self.req.status = "cancelada"
        self.req.save(update_fields=["status"])
        self.assertContains(self.lista(), "estado-cancelada")

    def test_la_lista_no_hace_una_consulta_extra_por_solicitud(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self.login(self.asis)
        url = reverse("request_list")
        with CaptureQueriesContext(connection) as una:
            self.client.get(url)
        for i in range(4):
            type(self.req).objects.create(
                executive=self.ejec, created_by=self.asis, title=f"Otra {i}", counterpart_name="X", duration_min=30,
                week_start=self.req.week_start,
            )
        with CaptureQueriesContext(connection) as varias:
            self.client.get(url)
        self.assertEqual(len(una), len(varias))
