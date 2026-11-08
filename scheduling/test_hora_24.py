"""Pruebas del formato de hora de 24 horas (TR-48): un solo formato en toda la aplicación. Internamente el cierre del día es la hora 24 y la persona lee "Fin del día"."""
import re
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from zoneinfo import ZoneInfo

from accounts.forms import HOURS_FROM, HOURS_TO
from meetings.forms import SchedulingRuleForm
from meetings.models import SchedulingRule
from meetings.test_proposal_views import ProposalViewBase

from .contracts import ProposedSlot
from .matching import END_OF_DAY, format_end_hour, format_hour, format_span, hour_choices
from .rules import RuleSpec, validate_rule
from .templatetags.scheduling_extras import rango_horario

LIMA = ZoneInfo("America/Lima")


class FormatoDeHoraTests(SimpleTestCase):
    def test_siempre_dos_digitos_y_24_horas(self):
        self.assertEqual([format_hour(h) for h in (0, 7, 9, 13, 23)], ["00:00", "07:00", "09:00", "13:00", "23:00"])

    def test_el_cierre_del_dia_se_escribe_como_fin_del_dia_en_las_frases(self):
        self.assertEqual(format_end_hour(24), "el fin del día")
        self.assertEqual(format_end_hour(18), "18:00")

    def test_un_rango_escribe_fin_del_dia_solo_si_termina_a_la_hora_24(self):
        self.assertEqual(format_span(9, 18), "09:00 a 18:00")
        self.assertEqual(format_span(8, 24), "08:00 hasta el fin del día")

    def test_las_opciones_de_inicio_van_de_00_a_23(self):
        opciones = hour_choices(0, 23)
        self.assertEqual((opciones[0], opciones[-1], len(opciones)), ((0, "00:00"), (23, "23:00"), 24))

    def test_las_opciones_de_fin_llegan_a_la_hora_24_que_se_lee_fin_del_dia(self):
        opciones = hour_choices(1, 24)
        self.assertEqual((opciones[0], opciones[-1], len(opciones)), ((1, "01:00"), (24, END_OF_DAY), 24))
        self.assertNotIn("24:00", [texto for _, texto in opciones])

    def test_el_registro_y_el_onboarding_usan_las_mismas_opciones(self):
        self.assertEqual(HOURS_FROM, hour_choices(0, 23))
        self.assertEqual(HOURS_TO, hour_choices(1, 24))

    def test_el_rango_de_una_propuesta_se_escribe_en_24_horas(self):
        inicio = datetime(2026, 10, 27, 15, 0, tzinfo=LIMA)
        slot = ProposedSlot(id="s", start=inicio, end=inicio + timedelta(minutes=45), reason="", rank=1)
        self.assertEqual(rango_horario(slot), "15:00 - 15:45")
        madrugada = datetime(2026, 10, 27, 0, 0, tzinfo=LIMA)
        self.assertEqual(rango_horario(ProposedSlot(id="s", start=madrugada, end=madrugada + timedelta(minutes=30), reason="", rank=1)), "00:00 - 00:30")


class FranjaDeLasReglasTests(SimpleTestCase):
    def test_el_cierre_del_dia_se_muestra_como_hasta_el_fin_del_dia(self):
        self.assertEqual(RuleSpec(None, 18, 24).range_text, "Desde 18:00 hasta el fin del día")

    def test_el_inicio_del_dia_se_muestra_como_desde_00_00(self):
        self.assertEqual(RuleSpec(None, 0, 10).range_text, "Desde 00:00 hasta 10:00")

    def test_un_dia_completo_va_de_00_00_al_fin_del_dia(self):
        self.assertEqual(RuleSpec(4, 0, 24).range_text, "Desde 00:00 hasta el fin del día")

    def test_las_frases_de_la_regla_no_cambian(self):
        self.assertEqual(RuleSpec(None, 0, 10).label, "nada antes de las 10:00")
        self.assertEqual(RuleSpec(None, 18, 24).label, "nada desde las 18:00")
        self.assertEqual(RuleSpec(None, 13, 14).label, "sin reuniones de 13:00 a 14:00")
        self.assertEqual(RuleSpec(4, 0, 24).label, "viernes protegido")


class FranjaDeLasReglasEnPantallaTests(ProposalViewBase):
    def setUp(self):
        super().setUp()
        self.regla = SchedulingRule.objects.create(executive=self.ejec, created_by=self.asis, weekday=None, start_hour=18, end_hour=24)
        self.login(self.asis)

    def test_la_lista_muestra_la_franja_con_hasta_el_fin_del_dia(self):
        r = self.client.get(reverse("rules"))
        self.assertContains(r, "Desde 18:00 hasta el fin del día")
        self.assertNotContains(r, "24:00")
        self.assertContains(r, "Nada desde las 18:00")

    def test_la_edicion_conserva_el_fin_del_dia_como_hora_de_fin(self):
        html = self.client.get(reverse("edit_rule", args=[self.regla.pk])).content.decode()
        self.assertRegex(html, r'<option value="24" selected>Fin del día</option>')
        self.assertNotIn("24:00", html)
        self.assertRegex(html, r'<option value="18" selected>18:00</option>')

    def test_el_formulario_ofrece_el_fin_del_dia_solo_como_hora_de_fin(self):
        form = SchedulingRuleForm(user=self.asis, executives=SchedulingRule.objects.none())
        self.assertNotIn((24, END_OF_DAY), form.fields["start_hour"].choices)
        self.assertIn((24, END_OF_DAY), form.fields["end_hour"].choices)

    def test_el_mensaje_de_validacion_no_menciona_24_00(self):
        self.assertEqual(validate_rule(None, 5, 5), "La hora de inicio debe ser menor que la de fin.")
        self.assertEqual(validate_rule(None, 5, 25), "Las horas deben estar entre 00:00 y el fin del día.")

    def test_se_puede_guardar_una_regla_que_termina_al_fin_del_dia(self):
        r = self.client.post(reverse("create_rule"), {"executive": self.ejec.pk, "weekday": "4", "start_hour": "14", "end_hour": "24"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(SchedulingRule.objects.filter(weekday=4, start_hour=14, end_hour=24).exists())

    def test_una_regla_que_termina_a_las_00_00_se_rechaza(self):
        r = self.client.post(reverse("create_rule"), {"executive": self.ejec.pk, "weekday": "4", "start_hour": "14", "end_hour": "0"})
        self.assertEqual(r.status_code, 400)


class UnSoloFormatoEnLasPlantillasTests(SimpleTestCase):
    """Ninguna plantilla ni vista escribe horas en formato de 12 horas (am/pm) ni sin cero inicial."""

    FORMATO_DE_HORA_PROHIBIDO = re.compile(r"[ghGAaPf]")

    def test_las_plantillas_usan_solo_H_e_i(self):
        patron = re.compile(r'\|(?:date|time):"([^"]*)"')
        revisados = 0
        for archivo in Path(settings.BASE_DIR, "templates").rglob("*.html"):
            for formato in patron.findall(archivo.read_text(encoding="utf-8")):
                revisados += 1
                sin_escapes = re.sub(r"\\.", "", formato)
                self.assertIsNone(self.FORMATO_DE_HORA_PROHIBIDO.search(sin_escapes), f"{archivo.name}: {formato}")
        self.assertGreater(revisados, 5)

    def test_el_codigo_no_usa_horas_de_12_horas(self):
        for carpeta in ("meetings", "scheduling", "accounts", "config"):
            for archivo in Path(settings.BASE_DIR, carpeta).rglob("*.py"):
                if archivo.name.startswith("test") or "migrations" in archivo.parts:
                    continue
                texto = archivo.read_text(encoding="utf-8")
                self.assertNotRegex(texto, r"%I|%p", archivo.name)
