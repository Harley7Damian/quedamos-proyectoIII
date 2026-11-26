"""Pruebas de los horarios flexibles: reglas con minutos y propuestas que empiezan cada 15 minutos."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from accounts.models import User
from meetings.models import AssistantLink, SchedulingRule

from .matching import AVAILABLE as A
from .proposal import build_proposal
from .rules import RuleSpec, validate_rule

LIMA = ZoneInfo("America/Lima")
LUNES = date(2026, 10, 26)
ANTES = datetime(2026, 10, 26, 6, 0, tzinfo=LIMA)
PW = "Secreto-12345"


def propose(exec_blocks, cp_blocks, duration=60, rules=(), now=ANTES):
    return build_proposal(
        request_id=7, title="Revisión", executive_name="Carla", counterpart_name="Pedro", duration_min=duration,
        week_start=LUNES, executive_blocks=exec_blocks, counterpart_blocks=cp_blocks, now=now, tz=LIMA, rules=rules,
    )


class ReglasConMinutosTests(SimpleTestCase):
    def test_nada_antes_de_las_0930_deja_empezar_a_esa_hora(self):
        regla = RuleSpec(None, 0, 9, end_minute=30)
        lunes = lambda h, m: datetime(2026, 10, 26, h, m, tzinfo=LIMA)
        self.assertTrue(regla.blocks(lunes(9, 0), lunes(9, 30)))
        self.assertTrue(regla.blocks(lunes(9, 15), lunes(10, 0)))
        self.assertFalse(regla.blocks(lunes(9, 30), lunes(10, 0)))

    def test_las_reglas_por_horas_completas_se_comportan_como_siempre(self):
        regla = RuleSpec(None, 13, 14)
        lunes = lambda h, m=0: datetime(2026, 10, 26, h, m, tzinfo=LIMA)
        self.assertTrue(regla.blocks(lunes(12, 30), lunes(13, 15)))
        self.assertFalse(regla.blocks(lunes(14), lunes(15)))
        self.assertFalse(regla.blocks(lunes(12), lunes(13)))

    def test_el_texto_incluye_los_minutos(self):
        self.assertEqual(RuleSpec(None, 0, 9, end_minute=30).label, "nada antes de las 09:30")
        self.assertEqual(RuleSpec(None, 17, 24, start_minute=45).label, "nada desde las 17:45")
        self.assertEqual(RuleSpec(4, 12, 14, start_minute=30, end_minute=15).label,
                         "sin reuniones de 12:30 a 14:15 los viernes")
        self.assertEqual(RuleSpec(None, 17, 24, start_minute=45).range_text, "Desde 17:45 hasta el fin del día")
        self.assertEqual(RuleSpec(None, 9, 12, end_minute=30).range_text, "Desde 09:00 hasta 12:30")
        self.assertEqual(RuleSpec(None, 18, 24).label, "nada desde las 18:00")  # sin cambios

    def test_validacion_de_minutos(self):
        self.assertIsNone(validate_rule(None, 9, 10, 15, 45))
        self.assertIn("00, 15, 30 o 45", validate_rule(None, 9, 10, 10, 0))
        self.assertIn("fin del día", validate_rule(None, 9, 24, 0, 30))
        self.assertIn("menor", validate_rule(None, 10, 10, 30, 15))
        self.assertIsNone(validate_rule(None, 10, 10, 15, 30))
        self.assertIsNone(validate_rule(4, 0, 24))
        self.assertIn("todos los horarios", validate_rule(None, 0, 24))


class PropuestaCada15MinutosTests(SimpleTestCase):
    def test_con_una_regla_hasta_las_0930_la_propuesta_empieza_a_las_0930(self):
        blocks = {"0-9": A, "0-10": A}
        p = propose(blocks, blocks, duration=30, rules=[RuleSpec(None, 0, 9, end_minute=30)])
        s = p.slots[0]
        self.assertEqual((s.start.hour, s.start.minute), (9, 30))
        self.assertEqual(s.id, "0-9-30")

    def test_antes_solo_podia_empezar_a_las_1000_ahora_aprovecha_la_media_hora(self):
        blocks = {"0-9": A, "0-10": A}
        p = propose(blocks, blocks, duration=60, rules=[RuleSpec(None, 0, 9, end_minute=30)])
        s = p.slots[0]
        self.assertEqual((s.start.hour, s.start.minute, s.end.hour, s.end.minute), (9, 30, 10, 30))

    def test_una_reunion_de_45_minutos_puede_empezar_en_un_cuarto_de_hora(self):
        blocks = {"1-14": A, "1-15": A}
        p = propose(blocks, blocks, duration=45, rules=[RuleSpec(None, 13, 14, end_minute=15)])
        self.assertEqual((p.slots[0].start.hour, p.slots[0].start.minute), (14, 15))

    def test_el_identificador_de_las_horas_en_punto_no_cambia(self):
        p = propose({"2-10": A}, {"2-10": A})
        self.assertEqual(p.slots[0].id, "2-10")

    def test_no_se_propone_algo_que_toca_una_hora_no_disponible(self):
        # 60 minutos a las 10:30 tocaría el bloque 11 que no está libre.
        blocks = {"0-10": A}
        p = propose(blocks, blocks, duration=60, rules=[RuleSpec(None, 0, 10, end_minute=30)])
        self.assertEqual(p.slots, [])

    def test_las_opciones_del_mismo_dia_no_quedan_pegadas(self):
        blocks = {f"0-{h}": A for h in range(9, 13)}
        p = propose(blocks, blocks, duration=30)
        horas = sorted((s.start.hour * 60 + s.start.minute) for s in p.slots)
        self.assertEqual(len(horas), 3)
        self.assertTrue(all(b - a >= 60 for a, b in zip(horas, horas[1:])))

    def test_si_no_alcanza_el_margen_se_completan_opciones_sin_pisarse(self):
        blocks = {"0-9": A}
        p = propose(blocks, blocks, duration=15)
        self.assertEqual([(s.start.hour, s.start.minute) for s in p.slots], [(9, 0), (9, 15), (9, 30)])

    def test_se_descarta_lo_que_ya_paso_con_precision_de_minutos(self):
        blocks = {"0-9": A, "0-10": A}
        ahora = datetime(2026, 10, 26, 9, 20, tzinfo=LIMA)
        p = propose(blocks, blocks, duration=30, now=ahora)
        self.assertEqual((p.slots[0].start.hour, p.slots[0].start.minute), (9, 30))

    def test_una_reunion_nunca_termina_despues_del_cierre_de_la_cuadricula(self):
        blocks = {"0-21": A}
        p = propose(blocks, blocks, duration=45)
        self.assertTrue(p.slots)
        self.assertTrue(all((s.end.hour, s.end.minute) <= (22, 0) for s in p.slots))


class ReglasConMinutosEnLaAppTests(TestCase):
    def setUp(self):
        self.ejec = User.objects.create_user(username="carla@x.com", email="carla@x.com", password=PW, full_name="Carla", role="ejecutivo")
        self.asis = User.objects.create_user(username="ana@x.com", email="ana@x.com", password=PW, full_name="Ana", role="asistente")
        AssistantLink.objects.create(assistant=self.asis, executive=self.ejec)
        self.client.login(username="ana@x.com", password=PW)

    def post(self, **over):
        data = {"executive": self.ejec.pk, "weekday": "", "start_hour": 0, "end_hour": 9, "end_minute": 30}
        data.update(over)
        return self.client.post(reverse("create_rule"), data)

    def test_se_crea_una_regla_con_minutos_y_se_lee_en_lenguaje_natural(self):
        self.assertEqual(self.post().status_code, 302)
        regla = SchedulingRule.objects.get()
        self.assertEqual((regla.end_hour, regla.end_minute), (9, 30))
        self.assertContains(self.client.get(reverse("rules")), "Nada antes de las 09:30")

    def test_sin_minutos_la_regla_es_por_horas_completas(self):
        self.client.post(reverse("create_rule"), {"executive": self.ejec.pk, "weekday": "", "start_hour": 13, "end_hour": 14})
        regla = SchedulingRule.objects.get()
        self.assertEqual((regla.start_minute, regla.end_minute), (0, 0))

    def test_rechaza_minutos_que_no_son_de_15_en_15(self):
        r = self.post(end_minute=10)
        self.assertEqual(r.status_code, 400)
        self.assertFalse(SchedulingRule.objects.exists())

    def test_rechaza_un_fin_de_dia_con_minutos(self):
        r = self.post(start_hour=18, end_hour=24, end_minute=15)
        self.assertContains(r, "fin del día", status_code=400)

    def test_el_formulario_muestra_selectores_de_minutos(self):
        html = self.client.get(reverse("rules")).content.decode()
        self.assertIn('name="start_minute"', html)
        self.assertIn('name="end_minute"', html)

    def test_editar_una_regla_conserva_y_cambia_los_minutos(self):
        self.post()
        regla = SchedulingRule.objects.get()
        r = self.client.post(reverse("edit_rule", args=[regla.pk]), {"weekday": "", "start_hour": 0, "end_hour": 10, "end_minute": 45})
        self.assertEqual(r.status_code, 302)
        regla.refresh_from_db()
        self.assertEqual((regla.end_hour, regla.end_minute), (10, 45))

    def test_la_base_de_datos_rechaza_minutos_invalidos(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            SchedulingRule.objects.create(executive=self.ejec, created_by=self.asis, start_hour=9, end_hour=10, end_minute=10)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SchedulingRule.objects.create(executive=self.ejec, created_by=self.asis, start_hour=10, end_hour=10, start_minute=30, end_minute=15)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SchedulingRule.objects.create(executive=self.ejec, created_by=self.asis, start_hour=18, end_hour=24, end_minute=15)
        SchedulingRule.objects.create(executive=self.ejec, created_by=self.asis, start_hour=10, end_hour=10, start_minute=15, end_minute=30)
