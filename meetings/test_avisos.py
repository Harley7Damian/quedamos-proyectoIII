"""Pruebas de los avisos visibles (TR-56): notificaciones flotantes y 'sin coincidencia' como aviso informativo."""
from django.contrib.staticfiles import finders
from django.urls import reverse

from .test_proposal_views import ProposalViewBase


class AvisosFlotantesTests(ProposalViewBase):
    """TR-56: los avisos son notificaciones flotantes y 'sin coincidencia' es informativo, no un error."""

    def test_los_avisos_se_muestran_como_notificacion_flotante_con_boton_para_cerrar(self):
        self.login(self.asis)
        r = self.generate(follow=True)
        self.assertContains(r, 'class="avisos"')
        self.assertContains(r, "data-aviso")
        self.assertContains(r, 'aria-label="Cerrar aviso"')

    def test_sin_coincidencia_llega_como_aviso_informativo_y_no_como_error(self):
        self.av("ejecutivo", {"0-9": 1})
        self.av("contraparte", {"1-9": 1})
        self.login(self.asis)
        r = self.generate(follow=True)
        self.assertContains(r, "aviso aviso-warning")
        self.assertNotContains(r, "aviso aviso-error")
        self.assertContains(r, "No hay un horario en que coincidan las dos partes")
        self.assertContains(r, "Amplía el rango")

    def test_un_error_real_sigue_mostrandose_como_error_y_con_rol_de_alerta(self):
        self.av("ejecutivo", {"0-9": 1})
        self.login(self.asis)
        r = self.generate(follow=True)
        self.assertContains(r, "aviso aviso-error")
        self.assertContains(r, 'role="alert"')

    def test_el_detalle_muestra_sin_coincidencia_como_resultado_informativo(self):
        self.av("ejecutivo", {"0-9": 1})
        self.av("contraparte", {"1-9": 1})
        self.req.status = "propuesta"  # propuesta vigente cuyos horarios ya no coinciden
        self.req.save(update_fields=["status"])
        self.login(self.asis)
        r = self.detail()
        self.assertContains(r, "msg-sin-coincidencia")
        self.assertContains(r, "Sin coincidencia de horarios")

    def test_la_pagina_carga_el_script_de_avisos(self):
        self.login(self.asis)
        self.assertContains(self.client.get(reverse("panel")), "js/avisos.js")
        self.assertIsNotNone(finders.find("js/avisos.js"))
