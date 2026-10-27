"""Pruebas de la propuesta de tres horarios (HU-06). Lógica pura: no toca la base de datos."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from .matching import AVAILABLE as A
from .matching import HIGH_PREF as P
from .proposal import build_proposal

LIMA = ZoneInfo("America/Lima")
LUNES = date(2026, 10, 26)
ANTES = datetime(2026, 10, 26, 6, 0, tzinfo=LIMA)  # antes de cualquier bloque de la semana


def propose(exec_blocks, cp_blocks, duration=60, now=ANTES):
    return build_proposal(
        request_id=7, title="Revisión", executive_name="Carla", counterpart_name="Pedro", duration_min=duration,
        week_start=LUNES, executive_blocks=exec_blocks, counterpart_blocks=cp_blocks, now=now, tz=LIMA,
    )


class CoincidenciaTests(SimpleTestCase):
    def test_sin_coincidencia_no_hay_opciones(self):
        p = propose({"0-9": A}, {"1-9": A})
        self.assertEqual(p.slots, [])

    def test_si_una_parte_no_marco_nada_no_hay_opciones(self):
        self.assertEqual(propose({}, {"0-9": A}).slots, [])
        self.assertEqual(propose({"0-9": A}, {}).slots, [])

    def test_una_sola_coincidencia_da_una_opcion(self):
        p = propose({"0-9": A, "0-10": A}, {"0-10": A, "3-9": A})
        self.assertEqual([(s.start.day, s.start.hour) for s in p.slots], [(26, 10)])

    def test_devuelve_a_lo_mucho_tres_opciones(self):
        blocks = {f"{d}-{h}": A for d in range(5) for h in (9, 10, 11)}
        self.assertEqual(len(propose(blocks, blocks).slots), 3)

    def test_los_datos_del_contrato_se_llenan(self):
        p = propose({"2-10": A}, {"2-10": A})
        self.assertEqual((p.request_id, p.title, p.counterpart_name, p.duration_min), ("7", "Revisión", "Pedro", 60))
        s = p.slots[0]
        self.assertEqual((s.rank, s.id), (1, "2-10"))
        self.assertEqual(s.start, datetime(2026, 10, 28, 10, 0, tzinfo=LIMA))
        self.assertEqual(s.end, datetime(2026, 10, 28, 11, 0, tzinfo=LIMA))
        self.assertIsNotNone(s.start.tzinfo)


class OrdenTests(SimpleTestCase):
    def test_la_preferencia_alta_de_ambos_va_primero(self):
        ej = {"0-9": A, "1-9": P, "2-9": P}
        cp = {"0-9": A, "1-9": A, "2-9": P}
        p = propose(ej, cp)
        self.assertEqual([s.id for s in p.slots], ["2-9", "1-9", "0-9"])
        self.assertEqual([s.rank for s in p.slots], [1, 2, 3])

    def test_a_igual_preferencia_gana_el_mas_temprano(self):
        p = propose({"3-9": A, "1-14": A}, {"3-9": A, "1-14": A})
        self.assertEqual([s.id for s in p.slots], ["1-14", "3-9"])

    def test_se_prefieren_dias_distintos_antes_que_dos_opciones_el_mismo_dia(self):
        ej = {"0-9": P, "0-10": P, "1-9": A, "2-9": A}
        p = propose(ej, dict(ej))
        self.assertEqual(sorted(s.start.day for s in p.slots), [26, 27, 28])

    def test_si_solo_hay_un_dia_se_completa_con_horas_distintas_de_ese_dia(self):
        blocks = {"0-9": A, "0-10": A, "0-11": A}
        p = propose(blocks, blocks)
        self.assertEqual(sorted(s.id for s in p.slots), ["0-10", "0-11", "0-9"])


class DuracionTests(SimpleTestCase):
    def test_noventa_minutos_exigen_dos_bloques_seguidos(self):
        ej = {"0-9": A, "0-10": A, "1-9": A, "1-11": A}
        p = propose(ej, dict(ej), duration=90)
        self.assertEqual([s.id for s in p.slots], ["0-9"])
        self.assertEqual(p.slots[0].end, datetime(2026, 10, 26, 10, 30, tzinfo=LIMA))

    def test_dos_horas_exigen_dos_bloques_seguidos_y_no_se_pisan_las_opciones(self):
        blocks = {f"0-{h}": A for h in (9, 10, 11, 12)}
        p = propose(blocks, blocks, duration=120)
        starts = sorted(s.start.hour for s in p.slots)
        self.assertEqual(starts, [9, 11])  # 9-11 y 11-13; 10-12 y 12-14 se pisarían

    def test_no_se_propone_una_reunion_que_termine_despues_del_horario(self):
        blocks = {"0-21": A}
        self.assertEqual(propose(blocks, blocks, duration=120).slots, [])
        self.assertEqual(len(propose(blocks, blocks, duration=60).slots), 1)

    def test_quince_y_treinta_minutos_usan_un_bloque(self):
        blocks = {"0-9": A}
        self.assertEqual(propose(blocks, blocks, duration=15).slots[0].end.minute, 15)
        self.assertEqual(propose(blocks, blocks, duration=30).slots[0].end.minute, 30)


class TiempoTests(SimpleTestCase):
    def test_no_se_proponen_horarios_que_ya_pasaron(self):
        blocks = {"0-9": A, "0-15": A, "1-9": A}
        ahora = datetime(2026, 10, 26, 12, 0, tzinfo=LIMA)
        p = propose(blocks, blocks, now=ahora)
        self.assertEqual(sorted(s.id for s in p.slots), ["0-15", "1-9"])

    def test_si_toda_la_semana_ya_paso_no_hay_opciones(self):
        blocks = {"0-9": A, "3-9": A}
        despues = datetime(2026, 11, 2, 8, 0, tzinfo=LIMA)
        self.assertEqual(propose(blocks, blocks, now=despues).slots, [])


class MotivoTests(SimpleTestCase):
    def reason(self, ej, cp, duration=60):
        return propose({"0-9": ej}, {"0-9": cp}, duration).slots[0].reason

    def test_ambos_disponibles(self):
        self.assertEqual(self.reason(A, A), "Carla y Pedro están disponibles.")

    def test_ambos_prefieren(self):
        self.assertEqual(self.reason(P, P), "Carla y Pedro lo marcaron como preferido.")

    def test_prefiere_el_ejecutivo(self):
        self.assertEqual(self.reason(P, A), "Carla lo marcó como preferido y Pedro también puede.")

    def test_prefiere_la_contraparte(self):
        self.assertEqual(self.reason(A, P), "Pedro lo marcó como preferido y Carla también puede.")

    def test_preferencia_parcial_en_una_reunion_de_dos_horas(self):
        p = propose({"0-9": P, "0-10": A}, {"0-9": A, "0-10": A}, duration=120)
        self.assertEqual(p.slots[0].reason, "Ambos pueden. Incluye horas que Carla prefiere.")

    def test_toda_opcion_tiene_motivo(self):
        blocks = {f"{d}-{h}": A for d in range(7) for h in (9, 10)}
        for s in propose(blocks, blocks).slots:
            self.assertTrue(s.reason.strip())
