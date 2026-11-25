"""Pruebas de la identidad de marca (nombre en cursiva autoalojado) y del rediseño de ingreso y registro."""
from pathlib import Path

from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse


class IdentidadDeMarcaTests(TestCase):
    def test_la_fuente_de_la_marca_esta_en_la_aplicacion_con_su_licencia(self):
        archivo = Path(finders.find("fonts/instrument-serif-latin-400-italic.woff2"))
        self.assertEqual(archivo.read_bytes()[:4], b"wOF2")
        self.assertLess(archivo.stat().st_size, 60_000)
        licencia = Path(finders.find("fonts/LICENSE-InstrumentSerif.txt")).read_text(encoding="utf-8")
        self.assertIn("SIL OPEN FONT LICENSE", licencia.upper())

    def test_la_hoja_de_identidad_declara_la_fuente_con_ruta_local_y_se_carga_en_las_paginas(self):
        css = Path(finders.find("css/identidad.css")).read_text(encoding="utf-8")
        self.assertIn('font-family: "Instrument Serif"', css)
        self.assertIn("font-display: swap", css)
        self.assertIn('url("../fonts/instrument-serif-latin-400-italic.woff2")', css)
        for ruta in ("landing", "login", "signup"):
            self.assertContains(self.client.get(reverse(ruta)), "css/identidad.css")

    def test_el_nombre_de_la_marca_lleva_la_clase_cursiva_en_cabecera_y_pie(self):
        self.assertContains(self.client.get(reverse("landing")), 'class="marca-nombre"', count=2)
        self.assertContains(self.client.get(reverse("login")), 'class="marca-nombre"', count=1)


class AccesoRediseñadoTests(TestCase):
    def test_ingreso_y_registro_muestran_el_panel_lateral_y_el_enlace_para_volver(self):
        for ruta in ("login", "signup"):
            with self.subTest(ruta=ruta):
                r = self.client.get(reverse(ruta))
                self.assertContains(r, 'class="acceso-lateral"')
                self.assertContains(r, "Menos mensajes")
                self.assertContains(r, f'href="{reverse("landing")}"')
                self.assertContains(r, "Volver al inicio")

    def test_las_etiquetas_no_llevan_dos_puntos_y_cada_campo_tiene_su_etiqueta_asociada(self):
        r = self.client.get(reverse("login"))
        self.assertContains(r, ">Correo electrónico</label>")
        self.assertContains(r, ">Contraseña</label>")
        self.assertNotContains(r, "Correo:")
        self.assertContains(r, 'for="id_username"')
        self.assertContains(r, 'for="id_password"')

    def test_el_registro_conserva_los_cuatro_campos_y_los_requisitos_de_la_clave(self):
        r = self.client.get(reverse("signup"))
        for nombre in ("full_name", "email", "password1", "password2"):
            self.assertContains(r, f'name="{nombre}"')
        self.assertContains(r, "data-requisitos")

    def test_los_iconos_de_los_campos_son_decorativos(self):
        r = self.client.get(reverse("login"))
        self.assertContains(r, 'class="icono" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"', count=2)
