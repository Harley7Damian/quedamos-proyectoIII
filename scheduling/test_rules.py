"""Pruebas de las reglas de horarios protegidos (HU-07). Lógica pura, sin base de datos."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from .matching import AVAILABLE as A
from .proposal import build_proposal
from .rules import RuleSpec, validate_rule

LIMA = ZoneInfo("America/Lima")
LUNES = date(2026, 10, 26)
ANTES = datetime(2026, 10, 26, 6, 0, tzinfo=LIMA)


def at(day, hour, minute=0):
    return datetime(2026, 10, 26 + day, hour, minute, tzinfo=LIMA)


class EtiquetaTests(SimpleTestCase):
    def test_nada_antes_de_una_hora(self):
        self.assertEqual(RuleSpec(None, 0, 10).label, "nada antes de las 10:00")

    def test_nada_desde_una_hora(self):
        self.assertEqual(RuleSpec(None, 18, 24).label, "nada desde las 18:00")

    def test_franja_intermedia(self):
        self.assertEqual(RuleSpec(None, 13, 14).label, "sin reuniones de 13:00 a 14:00")

    def test_dia_completo(self):
        self.assertEqual(RuleSpec(4, 0, 24).label, "viernes protegido")

    def test_franja_en_un_dia(self):
        self.assertEqual(RuleSpec(1, 15, 17).label, "sin reuniones de 15:00 a 17:00 los martes")
        self.assertEqual(RuleSpec(5, 0, 12).label, "nada antes de las 12:00 los sábados")


class BloqueoTests(SimpleTestCase):
    def test_empezar_justo_cuando_termina_la_franja_es_valido(self):
        self.assertFalse(RuleSpec(None, 0, 10).blocks(at(0, 10), at(0, 11)))

    def test_cruzar_el_limite_de_la_franja_se_bloquea(self):
        self.assertTrue(RuleSpec(None, 0, 10).blocks(at(0, 9, 30), at(0, 10, 30)))

    def test_terminar_justo_cuando_empieza_la_franja_es_valido(self):
        self.assertFalse(RuleSpec(None, 13, 14).blocks(at(0, 12), at(0, 13)))
        self.assertTrue(RuleSpec(None, 13, 14).blocks(at(0, 12, 30), at(0, 13, 30)))

    def test_una_reunion_dentro_de_la_franja_se_bloquea(self):
        self.assertTrue(RuleSpec(None, 13, 15).blocks(at(0, 13, 30), at(0, 14)))

    def test_una_regla_de_un_dia_no_afecta_a_los_otros(self):
        viernes = RuleSpec(4, 0, 24)
        self.assertTrue(viernes.blocks(at(4, 10), at(4, 11)))
        self.assertFalse(viernes.blocks(at(3, 10), at(3, 11)))

    def test_applies_on(self):
        self.assertTrue(RuleSpec(None, 0, 10).applies_on(at(2, 9)))
        self.assertTrue(RuleSpec(2, 0, 10).applies_on(at(2, 9)))
        self.assertFalse(RuleSpec(2, 0, 10).applies_on(at(3, 9)))


class ValidacionTests(SimpleTestCase):
    def test_reglas_validas(self):
        self.assertIsNone(validate_rule(None, 0, 10))
        self.assertIsNone(validate_rule(4, 0, 24))
        self.assertIsNone(validate_rule(None, 13, 14))

    def test_inicio_mayor_o_igual_al_fin(self):
        self.assertIn("menor", validate_rule(None, 10, 10))
        self.assertIn("menor", validate_rule(None, 15, 9))

    def test_horas_fuera_de_rango(self):
        self.assertIsNotNone(validate_rule(None, -1, 5))
        self.assertIsNotNone(validate_rule(None, 0, 25))
        self.assertIsNotNone(validate_rule(None, 24, 24))

    def test_dia_invalido(self):
        self.assertIsNotNone(validate_rule(7, 0, 10))

    def test_no_se_puede_bloquear_todo(self):
        self.assertIn("todos los horarios", validate_rule(None, 0, 24))


class PropuestaConReglasTests(SimpleTestCase):
    def propose(self, blocks, rules, duration=60):
        return build_proposal(
            request_id=1, title="t", executive_name="Carla", counterpart_name="Pedro", duration_min=duration,
            week_start=LUNES, executive_blocks=blocks, counterpart_blocks=dict(blocks), now=ANTES, tz=LIMA, rules=rules,
        )

    def test_ninguna_opcion_viola_una_regla(self):
        blocks = {f"{d}-{h}": A for d in range(5) for h in (8, 9, 10, 11)}
        p = self.propose(blocks, [RuleSpec(None, 0, 10)])
        self.assertTrue(p.slots)
        self.assertTrue(all(s.start.hour >= 10 for s in p.slots))

    def test_un_dia_protegido_queda_fuera(self):
        blocks = {f"{d}-10": A for d in (0, 4)}
        p = self.propose(blocks, [RuleSpec(4, 0, 24)])
        self.assertEqual([s.start.weekday() for s in p.slots], [0])

    def test_si_las_reglas_descartan_todo_no_hay_opciones(self):
        blocks = {"0-9": A, "4-9": A}
        self.assertEqual(self.propose(blocks, [RuleSpec(None, 0, 10), RuleSpec(4, 0, 24)]).slots, [])

    def test_una_reunion_larga_que_cruza_la_franja_se_descarta(self):
        blocks = {"0-9": A, "0-10": A, "0-11": A}
        p = self.propose(blocks, [RuleSpec(None, 0, 10)], duration=120)
        self.assertEqual([s.start.hour for s in p.slots], [10])

    def test_el_motivo_indica_las_reglas_que_aplican_ese_dia(self):
        blocks = {"0-11": A, "4-11": A}
        p = self.propose(blocks, [RuleSpec(None, 0, 10), RuleSpec(1, 0, 24)])
        self.assertTrue(p.slots)
        for s in p.slots:
            self.assertIn("Respeta: nada antes de las 10:00.", s.reason)
            self.assertNotIn("martes", s.reason)

    def test_el_motivo_lista_varias_reglas_del_mismo_dia(self):
        blocks = {"4-11": A}
        p = self.propose(blocks, [RuleSpec(None, 0, 10), RuleSpec(4, 13, 14)])
        self.assertIn("Respeta: nada antes de las 10:00; sin reuniones de 13:00 a 14:00 los viernes.", p.slots[0].reason)

    def test_sin_reglas_el_motivo_no_cambia(self):
        p = self.propose({"0-9": A}, [])
        self.assertNotIn("Respeta", p.slots[0].reason)
