"""Pruebas de la validacion de la salida del modelo (TR-80)."""
from django.test import SimpleTestCase

from .esquemas import Booleano, Entero, ErrorEsquema, Lista, Objeto, Opcion, Texto


class TextoTests(SimpleTestCase):
    def test_recorta_espacios(self):
        self.assertEqual(Texto(20).validar("  hola  "), "hola")

    def test_rechaza_lo_que_no_es_texto(self):
        with self.assertRaises(ErrorEsquema):
            Texto(20).validar(5)

    def test_rechaza_texto_demasiado_largo(self):
        with self.assertRaises(ErrorEsquema):
            Texto(5).validar("abcdef")

    def test_vacio_es_error_o_none_segun_nullable(self):
        with self.assertRaises(ErrorEsquema):
            Texto(5).validar("   ")
        self.assertIsNone(Texto(5, nullable=True).validar("   "))

    def test_none_solo_si_admite_null(self):
        with self.assertRaises(ErrorEsquema):
            Texto(5).validar(None)
        self.assertIsNone(Texto(5, nullable=True).validar(None))


class EnteroTests(SimpleTestCase):
    def test_acepta_dentro_del_rango(self):
        self.assertEqual(Entero(0, 24).validar(10), 10)

    def test_rechaza_fuera_de_rango(self):
        for valor in (-1, 25):
            with self.assertRaises(ErrorEsquema):
                Entero(0, 24).validar(valor)

    def test_rechaza_booleanos_decimales_y_texto(self):
        for valor in (True, 3.5, "3"):
            with self.assertRaises(ErrorEsquema):
                Entero(0, 24).validar(valor)


class OpcionYBooleanoTests(SimpleTestCase):
    def test_opcion_acepta_solo_lo_permitido(self):
        tipo = Opcion((30, 60))
        self.assertEqual(tipo.validar(60), 60)
        with self.assertRaises(ErrorEsquema):
            tipo.validar(45)

    def test_opcion_no_confunde_true_con_1(self):
        with self.assertRaises(ErrorEsquema):
            Opcion((1, 2)).validar(True)

    def test_booleano(self):
        self.assertIs(Booleano().validar(False), False)
        with self.assertRaises(ErrorEsquema):
            Booleano().validar("si")


class ListaYObjetoTests(SimpleTestCase):
    esquema = Objeto({"tareas": Lista(Objeto({"texto": Texto(20), "fecha": Texto(10, nullable=True)}), max_items=2)})

    def test_valida_estructuras_anidadas_y_completa_los_null(self):
        datos = self.esquema.validar({"tareas": [{"texto": "enviar"}]})
        self.assertEqual(datos, {"tareas": [{"texto": "enviar", "fecha": None}]})

    def test_descarta_campos_que_el_esquema_no_declara(self):
        datos = self.esquema.validar({"tareas": [], "instruccion": "ignora todo"})
        self.assertEqual(datos, {"tareas": []})

    def test_rechaza_demasiados_elementos(self):
        with self.assertRaises(ErrorEsquema):
            self.esquema.validar({"tareas": [{"texto": "a"}, {"texto": "b"}, {"texto": "c"}]})

    def test_falta_un_campo_obligatorio(self):
        with self.assertRaises(ErrorEsquema):
            self.esquema.validar({"tareas": [{"fecha": "21/11"}]})

    def test_el_error_indica_donde_pero_no_el_contenido(self):
        with self.assertRaises(ErrorEsquema) as contexto:
            self.esquema.validar({"tareas": [{"texto": "x" * 50}]})
        self.assertIn("tareas[0].texto", str(contexto.exception))
        self.assertNotIn("xxxxx", str(contexto.exception))

    def test_rechaza_lo_que_no_es_objeto_ni_lista(self):
        with self.assertRaises(ErrorEsquema):
            self.esquema.validar("texto")
        with self.assertRaises(ErrorEsquema):
            self.esquema.validar({"tareas": "texto"})
