"""Pruebas de las reglas de horarios protegidos en pantalla (HU-07): permisos, validación y efecto en la propuesta."""
from datetime import date, datetime
from unittest import mock
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .models import AssistantLink, Availability, MeetingRequest, SchedulingRule

PW = "Secreto-12345"
LIMA = ZoneInfo("America/Lima")


def mk(email, name, role):
    return User.objects.create_user(username=email, email=email, password=PW, full_name=name, role=role)


class RulesBase(TestCase):
    def setUp(self):
        self.ejec = mk("carla@x.com", "Carla Ejecutiva", "ejecutivo")
        self.ejec2 = mk("luis@x.com", "Luis Ejecutivo", "ejecutivo")
        self.asis = mk("ana@x.com", "Ana Asistente", "asistente")
        self.otra = mk("otra@x.com", "Otra Asistente", "asistente")
        AssistantLink.objects.create(assistant=self.asis, executive=self.ejec)

    def login(self, user):
        self.client.logout()
        self.assertTrue(self.client.login(username=user.username, password=PW))

    def make_rule(self, executive=None, weekday=None, start=0, end=10, active=True):
        return SchedulingRule.objects.create(
            executive=executive or self.ejec, created_by=self.asis, weekday=weekday,
            start_hour=start, end_hour=end, active=active)

    def post_rule(self, **over):
        data = {"executive": self.ejec.pk, "weekday": "", "start_hour": 0, "end_hour": 10}
        data.update(over)
        return self.client.post(reverse("create_rule"), data)


class CrudTests(RulesBase):
    def test_la_asistente_crea_una_regla_para_su_ejecutivo(self):
        self.login(self.asis)
        r = self.post_rule()
        self.assertEqual(r.status_code, 302)
        rule = SchedulingRule.objects.get()
        self.assertEqual((rule.executive, rule.created_by, rule.weekday, rule.start_hour, rule.end_hour, rule.active),
                         (self.ejec, self.asis, None, 0, 10, True))

    def test_la_lista_muestra_la_regla_en_lenguaje_natural(self):
        self.make_rule(weekday=4, start=0, end=24)
        self.login(self.asis)
        self.assertContains(self.client.get(reverse("rules")), "Viernes protegido")

    def test_no_se_puede_crear_para_un_ejecutivo_sin_vinculo(self):
        self.login(self.asis)
        r = self.post_rule(executive=self.ejec2.pk)
        self.assertEqual(r.status_code, 400)
        self.assertFalse(SchedulingRule.objects.exists())

    def test_el_ejecutivo_puede_crear_sus_propias_reglas(self):
        self.login(self.ejec)
        r = self.post_rule()
        self.assertEqual(r.status_code, 302)
        self.assertEqual(SchedulingRule.objects.get().executive, self.ejec)

    def test_el_creador_lo_define_el_servidor(self):
        self.login(self.asis)
        self.post_rule(created_by=self.ejec2.pk)
        self.assertEqual(SchedulingRule.objects.get().created_by, self.asis)

    def test_validaciones(self):
        self.login(self.asis)
        for over in ({"start_hour": 10, "end_hour": 10}, {"start_hour": 15, "end_hour": 9},
                     {"start_hour": 0, "end_hour": 24}, {"start_hour": 30}, {"end_hour": 0}, {"weekday": 9}):
            self.assertEqual(self.post_rule(**over).status_code, 400, over)
        self.assertFalse(SchedulingRule.objects.exists())

    def test_un_dia_completo_es_valido_pero_todos_los_dias_completos_no(self):
        self.login(self.asis)
        self.assertEqual(self.post_rule(weekday=4, start_hour=0, end_hour=24).status_code, 302)
        r = self.post_rule(weekday="", start_hour=0, end_hour=24)
        self.assertContains(r, "bloquearía todos los horarios", status_code=400)

    def test_la_base_de_datos_rechaza_horas_invalidas(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            SchedulingRule.objects.create(executive=self.ejec, created_by=self.asis, start_hour=12, end_hour=12)

    def test_editar_cambia_la_regla(self):
        rule = self.make_rule(start=0, end=10)
        self.login(self.asis)
        r = self.client.post(reverse("edit_rule", args=[rule.pk]), {"weekday": "2", "start_hour": 8, "end_hour": 12})
        self.assertEqual(r.status_code, 302)
        rule.refresh_from_db()
        self.assertEqual((rule.weekday, rule.start_hour, rule.end_hour), (2, 8, 12))
        self.assertEqual(rule.executive, self.ejec)

    def test_editar_con_datos_invalidos_no_guarda(self):
        rule = self.make_rule(start=0, end=10)
        self.login(self.asis)
        r = self.client.post(reverse("edit_rule", args=[rule.pk]), {"weekday": "", "start_hour": 12, "end_hour": 11})
        self.assertEqual(r.status_code, 400)
        rule.refresh_from_db()
        self.assertEqual((rule.start_hour, rule.end_hour), (0, 10))

    def test_la_pagina_de_edicion_muestra_los_valores_actuales(self):
        rule = self.make_rule(weekday=4, start=13, end=15)
        self.login(self.asis)
        html = self.client.get(reverse("edit_rule", args=[rule.pk])).content.decode()
        self.assertIn('<option value="4" selected>', html)
        self.assertIn('<option value="13" selected>', html)
        self.assertIn('<option value="15" selected>', html)

    def test_desactivar_y_volver_a_activar(self):
        rule = self.make_rule()
        self.login(self.asis)
        self.client.post(reverse("toggle_rule", args=[rule.pk]))
        rule.refresh_from_db()
        self.assertFalse(rule.active)
        self.client.post(reverse("toggle_rule", args=[rule.pk]))
        rule.refresh_from_db()
        self.assertTrue(rule.active)

    def test_alternar_exige_post(self):
        rule = self.make_rule()
        self.login(self.asis)
        self.assertEqual(self.client.get(reverse("toggle_rule", args=[rule.pk])).status_code, 405)


class PermisosTests(RulesBase):
    def test_una_asistente_sin_vinculo_no_ve_ni_toca_las_reglas(self):
        rule = self.make_rule()
        self.login(self.otra)
        self.assertNotContains(self.client.get(reverse("rules")), "Nada antes de las 10:00")
        self.assertEqual(self.client.get(reverse("edit_rule", args=[rule.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("edit_rule", args=[rule.pk]), {"start_hour": 1, "end_hour": 2}).status_code, 404)
        self.assertEqual(self.client.post(reverse("toggle_rule", args=[rule.pk])).status_code, 404)
        rule.refresh_from_db()
        self.assertTrue(rule.active)

    def test_la_asistente_no_ve_las_reglas_de_otro_ejecutivo(self):
        self.make_rule(executive=self.ejec2, start=0, end=7)
        self.login(self.asis)
        response = self.client.get(reverse("rules"))
        self.assertNotContains(response, "Nada antes de las 07:00")
        self.assertNotContains(response, "Luis Ejecutivo")

    def test_al_desvincular_se_pierde_el_acceso_a_las_reglas(self):
        rule = self.make_rule()
        AssistantLink.objects.all().delete()
        self.login(self.asis)
        self.assertEqual(self.client.get(reverse("edit_rule", args=[rule.pk])).status_code, 404)

    def test_el_anonimo_es_enviado_al_ingreso(self):
        self.assertEqual(self.client.get(reverse("rules")).status_code, 302)
        self.assertEqual(self.client.post(reverse("create_rule"), {}).status_code, 302)


class EfectoEnLaPropuestaTests(RulesBase):
    def setUp(self):
        super().setUp()
        self.req = MeetingRequest.objects.create(
            executive=self.ejec, created_by=self.asis, title="Revisión", counterpart_name="Pedro Gómez",
            duration_min=60, week_start=date(2026, 10, 26))
        blocks = {"0-9": 1, "0-11": 1, "4-11": 1}
        for party in ("ejecutivo", "contraparte"):
            Availability.objects.create(request=self.req, party=party, blocks=blocks)
        patcher = mock.patch("django.utils.timezone.now", return_value=datetime(2026, 10, 26, 6, 0, tzinfo=LIMA))
        patcher.start()
        self.addCleanup(patcher.stop)

    def generate(self):
        self.login(self.asis)
        return self.client.post(reverse("generate_proposal", args=[self.req.pk]), follow=True)

    def test_sin_reglas_se_proponen_todos_los_horarios_coincidentes(self):
        r = self.generate()
        self.assertContains(r, "Opción 3")
        self.assertContains(r, "09:00 - 10:00")

    def test_con_una_regla_activa_ninguna_opcion_la_viola_y_se_indica(self):
        self.make_rule(start=0, end=10)
        r = self.generate()
        self.assertNotContains(r, "09:00 - 10:00")
        self.assertContains(r, "Respeta: nada antes de las 10:00.")
        self.assertContains(r, "Opción 2")
        self.assertNotContains(r, "Opción 3")

    def test_una_regla_desactivada_no_se_aplica(self):
        self.make_rule(start=0, end=10, active=False)
        self.assertContains(self.generate(), "09:00 - 10:00")

    def test_la_regla_de_otro_ejecutivo_no_se_aplica(self):
        self.make_rule(executive=self.ejec2, start=0, end=24, weekday=0)
        self.assertContains(self.generate(), "09:00 - 10:00")

    def test_si_las_reglas_descartan_todo_el_mensaje_apunta_a_las_reglas(self):
        self.make_rule(weekday=0, start=0, end=24)
        self.make_rule(weekday=4, start=0, end=24)
        r = self.generate()
        self.assertContains(r, "las reglas protegidas del ejecutivo los descartan")
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "pendiente")

    def test_si_no_hay_coincidencia_ni_reglas_el_mensaje_es_el_de_ampliar(self):
        Availability.objects.filter(party="contraparte").update(blocks={"3-15": 1})
        r = self.generate()
        self.assertContains(r, "Amplía el rango")
        self.assertNotContains(r, "las reglas protegidas")

    def test_el_detalle_lista_las_reglas_activas(self):
        self.make_rule(start=0, end=10)
        self.make_rule(weekday=4, start=0, end=24, active=False)
        self.login(self.asis)
        html = self.client.get(reverse("request_detail", args=[self.req.pk])).content.decode()
        self.assertIn("Reglas activas del ejecutivo: nada antes de las 10:00.", html)
        self.assertNotIn("viernes protegido", html)
