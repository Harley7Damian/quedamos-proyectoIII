"""Pruebas de las métricas de uso (HU-10): contadores, cálculo, rotulado de lo estimado y visibilidad."""
from datetime import timedelta

from django.urls import reverse

from scheduling.templatetags.scheduling_extras import duracion

from .metrics import BASELINE_MESSAGES, meeting_metric, summarize
from .models import MeetingRequest
from .test_confirmation import ConfirmBase


class CounterTests(ConfirmBase):
    """setUp deja la solicitud con una propuesta generada, sin enlaces generados todavía."""

    def refreshed(self):
        self.req.refresh_from_db()
        return self.req

    def test_al_generar_la_primera_propuesta_hay_una_ronda(self):
        self.assertEqual(self.refreshed().proposal_rounds, 1)

    def test_cada_propuesta_nueva_suma_una_ronda(self):
        self.login(self.asis)
        self.generate()
        self.assertEqual(self.refreshed().proposal_rounds, 2)

    def test_una_propuesta_sin_coincidencia_no_suma_ronda(self):
        self.av("contraparte", {"4-20": 1})
        self.login(self.asis)
        self.generate()
        req = self.refreshed()
        self.assertEqual(req.status, "pendiente")
        self.assertEqual(req.proposal_rounds, 1)

    def test_generar_el_enlace_de_la_contraparte_suma_un_enlace(self):
        self.login(self.asis)
        self.client.post(reverse("create_counterpart_link", args=[self.req.pk]))
        self.assertEqual(self.refreshed().links_shared, 1)

    def test_generar_el_enlace_de_aprobacion_suma_un_enlace(self):
        self.login(self.asis)
        self.client.post(reverse("create_approval_link", args=[self.req.pk]))
        self.assertEqual(self.refreshed().links_shared, 1)

    def test_un_enlace_rechazado_no_suma(self):
        self.login(self.otra)
        self.client.post(reverse("create_approval_link", args=[self.req.pk]))
        self.assertEqual(self.refreshed().links_shared, 0)


class MetricCalculationTests(ConfirmBase):
    def approved(self, hours=5, links=2, rounds=1):
        self.req.refresh_from_db()
        req = self.req if self.req.is_approved else self.approve()
        MeetingRequest.objects.filter(pk=req.pk).update(
            created_at=req.decided_at - timedelta(hours=hours), links_shared=links, proposal_rounds=rounds
        )
        req.refresh_from_db()
        return req

    def test_una_reunion_sin_aprobar_no_tiene_metricas(self):
        with self.assertRaises(ValueError):
            meeting_metric(self.req)

    def test_el_tiempo_hasta_confirmar_es_decision_menos_creacion(self):
        metric = meeting_metric(self.approved(hours=5))
        self.assertEqual(metric.time_to_confirm, timedelta(hours=5))

    def test_los_mensajes_evitados_restan_los_enlaces_a_la_referencia(self):
        self.assertEqual(meeting_metric(self.approved(links=2)).avoided, BASELINE_MESSAGES - 2)

    def test_los_mensajes_evitados_nunca_son_negativos(self):
        self.assertEqual(meeting_metric(self.approved(links=BASELINE_MESSAGES + 4)).avoided, 0)

    def test_el_resumen_sin_reuniones_solo_informa_que_no_hay(self):
        self.assertEqual(summarize([]), {"count": 0})

    def test_el_resumen_calcula_promedio_mediana_y_total(self):
        primera = meeting_metric(self.approved(hours=2, links=2, rounds=1))
        segunda = meeting_metric(self.approved(hours=6, links=3, rounds=2))
        resumen = summarize([primera, segunda])
        self.assertEqual(resumen["count"], 2)
        self.assertEqual(resumen["mean_time"], timedelta(hours=4))
        self.assertEqual(resumen["median_time"], timedelta(hours=4))
        self.assertEqual(resumen["mean_rounds"], 1.5)
        self.assertEqual(resumen["avoided_total"], (BASELINE_MESSAGES - 2) + (BASELINE_MESSAGES - 3))


class DurationFilterTests(ConfirmBase):
    def test_formatos_de_duracion(self):
        self.assertEqual(duracion(timedelta(seconds=20)), "menos de 1 min")
        self.assertEqual(duracion(timedelta(minutes=12)), "12 min")
        self.assertEqual(duracion(timedelta(hours=4, minutes=5)), "4 h 5 min")
        self.assertEqual(duracion(timedelta(days=2, hours=3)), "2 d 3 h")


class MetricsViewTests(ConfirmBase):
    def url(self):
        return reverse("metrics")

    def test_sin_reuniones_confirmadas_muestra_el_estado_vacio(self):
        self.login(self.asis)
        self.assertContains(self.client.get(self.url()), "Aún no hay reuniones confirmadas para medir")

    def test_la_reunion_confirmada_aparece_con_sus_cifras(self):
        req = self.approve()
        MeetingRequest.objects.filter(pk=req.pk).update(created_at=req.decided_at - timedelta(hours=5), links_shared=2)
        self.login(self.asis)
        r = self.client.get(self.url())
        self.assertContains(r, "Revisión trimestral")
        self.assertContains(r, "5 h 0 min")
        self.assertContains(r, f"<td class=\"num\">{BASELINE_MESSAGES - 2}</td>")

    def test_lo_estimado_se_rotula_y_se_declara_como_supuesto(self):
        self.approve()
        self.login(self.asis)
        r = self.client.get(self.url())
        self.assertContains(r, "estimado")
        self.assertContains(r, "supuesto del equipo")
        self.assertContains(r, f"{BASELINE_MESSAGES} mensajes")

    def test_el_ejecutivo_ve_las_suyas(self):
        self.approve()
        self.login(self.ejec)
        self.assertContains(self.client.get(self.url()), "Revisión trimestral")

    def test_una_asistente_sin_vinculo_no_ve_reuniones_ajenas(self):
        self.approve()
        self.login(self.otra)
        self.assertNotContains(self.client.get(self.url()), "Revisión trimestral")

    def test_el_anonimo_es_enviado_a_ingresar(self):
        r = self.client.get(self.url())
        self.assertEqual(r.status_code, 302)
        self.assertIn("/acceso/", r["Location"])

    def test_la_barra_lateral_enlaza_a_las_metricas(self):
        self.login(self.asis)
        self.assertContains(self.client.get(reverse("panel")), self.url())

    def test_no_expone_notas_ni_correos_de_la_contraparte(self):
        MeetingRequest.objects.filter(pk=self.req.pk).update(notes="Nota privada", counterpart_email="pedro@cliente.com")
        self.approve()
        self.login(self.asis)
        r = self.client.get(self.url())
        self.assertNotContains(r, "Nota privada")
        self.assertNotContains(r, "pedro@cliente.com")
