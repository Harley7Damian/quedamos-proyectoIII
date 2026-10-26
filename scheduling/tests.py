from django.test import SimpleTestCase  # no toca la base de datos: lógica pura

from .matching import (
    AVAILABLE,
    HIGH_PREF,
    UNAVAILABLE,
    Member,
    block_key,
    compute_block_scores,
    format_block_label,
    format_hour,
    get_suggestions,
)


def mk_member(id_, name, submitted=True, availability=None, is_demo=False):
    return Member(id=id_, name=name, submitted=submitted, availability=availability or {}, is_demo=is_demo)


class ComputeBlockScoresTests(SimpleTestCase):
    def test_sin_integrantes_no_hay_bloques(self):
        self.assertEqual(compute_block_scores([]), [])

    def test_integrante_que_no_respondio_no_cuenta(self):
        pendiente = mk_member("1", "Pendiente", submitted=False, availability={block_key(0, 9): HIGH_PREF})
        self.assertEqual(compute_block_scores([pendiente]), [])

    def test_un_bloque_disponible_de_un_solo_integrante_es_coincidencia_total(self):
        key = block_key(0, 9)
        m = mk_member("1", "Ana", availability={key: AVAILABLE})
        scores = compute_block_scores([m])
        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0].available_count, 1)
        self.assertEqual(scores[0].high_pref_count, 0)
        self.assertTrue(scores[0].is_full_match)

    def test_preferencia_alta_cuenta_como_disponibilidad_y_como_preferencia(self):
        key = block_key(2, 15)
        a = mk_member("1", "Ana", availability={key: AVAILABLE})
        b = mk_member("2", "Luis", availability={key: HIGH_PREF})
        scores = compute_block_scores([a, b])
        self.assertEqual(scores[0].available_count, 2)
        self.assertEqual(scores[0].high_pref_count, 1)
        self.assertTrue(scores[0].is_full_match)

    def test_bloque_sin_nadie_disponible_se_omite(self):
        key = block_key(0, 9)
        m = mk_member("1", "Ana", availability={key: UNAVAILABLE})
        self.assertEqual(compute_block_scores([m]), [])

    def test_coincidencia_parcial_no_es_coincidencia_total(self):
        key = block_key(0, 9)
        a = mk_member("1", "Ana", availability={key: AVAILABLE})
        b = mk_member("2", "Luis", availability={key: UNAVAILABLE})
        scores = compute_block_scores([a, b])
        self.assertEqual(scores[0].available_count, 1)
        self.assertFalse(scores[0].is_full_match)

    def test_orden_principal_por_cantidad_de_disponibles(self):
        key_mas = block_key(0, 9)
        key_menos = block_key(0, 10)
        a = mk_member("1", "Ana", availability={key_mas: AVAILABLE, key_menos: AVAILABLE})
        b = mk_member("2", "Luis", availability={key_mas: AVAILABLE})
        scores = compute_block_scores([a, b])
        self.assertEqual(scores[0].key, key_mas)
        self.assertEqual(scores[0].available_count, 2)

    def test_desempate_por_preferencia_alta(self):
        key_con_estrella = block_key(1, 14)
        key_sin_estrella = block_key(1, 15)
        a = mk_member("1", "Ana", availability={key_con_estrella: HIGH_PREF, key_sin_estrella: AVAILABLE})
        b = mk_member("2", "Luis", availability={key_con_estrella: AVAILABLE, key_sin_estrella: AVAILABLE})
        scores = compute_block_scores([a, b])
        # Ambos bloques tienen available_count=2, pero el primero tiene 1 preferencia alta.
        self.assertEqual(scores[0].key, key_con_estrella)
        self.assertEqual(scores[0].high_pref_count, 1)

    def test_integrante_demo_pondera_igual_que_uno_real(self):
        key = block_key(0, 9)
        real = mk_member("1", "Ana", availability={key: AVAILABLE})
        demo = mk_member("2", "Ejemplo", availability={key: AVAILABLE}, is_demo=True)
        scores = compute_block_scores([real, demo])
        self.assertEqual(scores[0].available_count, 2)
        self.assertTrue(scores[0].is_full_match)


class GetSuggestionsTests(SimpleTestCase):
    def test_limit_recorta_la_lista_de_mejores_bloques(self):
        a = mk_member("1", "Ana", availability={
            block_key(0, 9): AVAILABLE,
            block_key(0, 10): AVAILABLE,
            block_key(0, 11): AVAILABLE,
        })
        suggestions = get_suggestions([a], limit=2)
        self.assertEqual(len(suggestions.top), 2)

    def test_total_count_incluye_a_quien_no_ha_respondido_pero_responded_count_no(self):
        respondio = mk_member("1", "Ana", availability={block_key(0, 9): AVAILABLE})
        falta = mk_member("2", "Luis", submitted=False)
        suggestions = get_suggestions([respondio, falta])
        self.assertEqual(suggestions.responded_count, 1)
        self.assertEqual(suggestions.total_count, 2)
        self.assertTrue(suggestions.has_full_match)  # coincidencia total entre quienes sí respondieron


class FormatHelpersTests(SimpleTestCase):
    def test_formato_de_hora_y_etiqueta_de_bloque(self):
        self.assertEqual(format_hour(9), "09:00")
        self.assertEqual(format_block_label(0, 9), "Lunes · 09:00 - 10:00")