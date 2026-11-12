"""Pruebas del recorrido por pasos (TR-57): el detalle muestra el avance en seis pasos sin cambiar el flujo."""
from .pasos import pasos_de
from .test_approval import ApprovalBase


class RecorridoPorPasosTests(ApprovalBase):
    """TR-57: el detalle muestra el avance en seis pasos sin cambiar el flujo."""

    NOMBRES = ["Solicitud creada", "Enlace a la contraparte", "Disponibilidades", "Propuesta", "Aprobación", "Confirmada"]

    def pasos(self, solicitud=None, ej=True, cp=True):
        return pasos_de(solicitud or self.req, ej, cp)

    def estados(self, **kw):
        return [p.estado for p in self.pasos(**kw)]

    def test_hay_seis_pasos_en_orden(self):
        self.assertEqual([p.nombre for p in self.pasos()], self.NOMBRES)

    def test_solicitud_nueva_esta_en_el_enlace_a_la_contraparte(self):
        self.req.status = "pendiente"
        self.assertEqual(self.estados(ej=False, cp=False), ["hecho", "actual", "pendiente", "pendiente", "pendiente", "pendiente"])

    def test_respondio_la_contraparte_falta_la_del_ejecutivo(self):
        self.req.status = "pendiente"
        self.assertEqual(self.estados(ej=False, cp=True), ["hecho", "hecho", "actual", "pendiente", "pendiente", "pendiente"])

    def test_con_ambas_disponibilidades_toca_generar_la_propuesta(self):
        self.req.status = "pendiente"
        self.assertEqual(self.estados(), ["hecho", "hecho", "hecho", "actual", "pendiente", "pendiente"])

    def test_con_propuesta_toca_la_aprobacion(self):
        self.assertEqual(self.estados(), ["hecho", "hecho", "hecho", "hecho", "actual", "pendiente"])

    def test_aprobada_deja_todo_completado(self):
        self.req.status = "aprobada"
        self.assertEqual(self.estados(), ["hecho"] * 6)

    def test_pidio_otras_opciones_vuelve_a_la_propuesta(self):
        self.req.request_new_options()
        pasos = self.pasos()
        self.assertEqual([p.estado for p in pasos], ["hecho", "hecho", "hecho", "actual", "pendiente", "pendiente"])
        self.assertIn("otras opciones", pasos[3].ayuda)

    def test_una_cancelada_no_tiene_recorrido(self):
        self.req.status = "cancelada"
        self.assertEqual(self.pasos(), [])

    def test_solo_hay_un_paso_actual_y_solo_ese_lleva_ayuda(self):
        for estado in ("pendiente", "propuesta"):
            self.req.status = estado
            pasos = self.pasos(ej=False, cp=False)
            self.assertEqual(sum(p.estado == "actual" for p in pasos), 1)
            self.assertEqual([p.nombre for p in pasos if p.ayuda], [p.nombre for p in pasos if p.estado == "actual"])

    def test_el_detalle_muestra_el_recorrido_y_marca_el_paso_actual(self):
        self.login(self.asis)
        r = self.detail()
        self.assertContains(r, 'class="pasos"')
        for nombre in self.NOMBRES:
            self.assertContains(r, nombre)
        self.assertContains(r, 'aria-current="step"')
        self.assertContains(r, "paso actual")

    def test_el_detalle_conserva_las_secciones_y_botones_del_flujo(self):
        self.login(self.asis)
        r = self.detail()
        for texto in (
            "1. Disponibilidad del ejecutivo", "2. Disponibilidad de la contraparte", "3. Propuesta de horarios",
            "Generar enlace para la contraparte", "Generar enlace de aprobación para el ejecutivo",
            "Guardar disponibilidad del ejecutivo",
        ):
            self.assertContains(r, texto)

    def test_el_ejecutivo_tambien_ve_el_recorrido(self):
        self.login(self.ejec)
        self.assertContains(self.detail(), 'class="pasos"')

    def test_una_cancelada_no_pinta_el_recorrido_en_el_detalle(self):
        self.req.status = "cancelada"
        self.req.save(update_fields=["status"])
        self.login(self.asis)
        self.assertNotContains(self.detail(), 'class="pasos"')
