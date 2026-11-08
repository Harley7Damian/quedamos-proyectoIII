"""Pruebas de la tipografía autoalojada (TR-49): la fuente sale de la aplicación y no se pide nada a dominios externos."""
import re
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import TestCase

FUENTE = "fonts/inter-latin-wght-normal.woff2"
RECURSOS_EXTERNOS = re.compile(r"fonts\.googleapis|fonts\.gstatic|use\.typekit|use\.fontawesome|fontawesome\.com|cdnjs|bootstrapcdn|jsdelivr|unpkg")


class TipografiaAutoalojadaTests(TestCase):
    def ruta_estatica(self, nombre):
        return Path(finders.find(nombre))

    def test_el_archivo_de_la_fuente_esta_en_la_aplicacion_y_es_woff2(self):
        archivo = self.ruta_estatica(FUENTE)
        self.assertEqual(archivo.read_bytes()[:4], b"wOF2")
        self.assertLess(archivo.stat().st_size, 120_000)

    def test_la_licencia_de_la_fuente_se_entrega_junto_al_archivo(self):
        licencia = self.ruta_estatica("fonts/LICENSE-Inter.txt").read_text(encoding="utf-8")
        self.assertIn("SIL OPEN FONT LICENSE", licencia.upper())

    def test_la_hoja_de_estilos_declara_la_fuente_con_una_ruta_local_que_existe(self):
        css = self.ruta_estatica("css/app.css").read_text(encoding="utf-8")
        declaracion = re.search(r"@font-face\s*\{[^}]*\}", css).group(0)
        self.assertIn('font-family: "Inter"', declaracion)
        self.assertIn("font-display: swap", declaracion)
        rutas = re.findall(r'url\("([^"]+)"\)', declaracion)
        self.assertTrue(rutas)
        for ruta in rutas:
            self.assertFalse(ruta.startswith(("http:", "https:", "//")), ruta)
            self.assertTrue((self.ruta_estatica("css/app.css").parent / ruta).resolve().exists(), ruta)

    def test_el_texto_de_la_pagina_y_los_titulos_de_la_landing_usan_inter(self):
        self.assertRegex(self.ruta_estatica("css/app.css").read_text(encoding="utf-8"), r'body \{[^}]*font-family: "Inter", system-ui')
        self.assertIn('font-family:"Inter"', self.ruta_estatica("css/landing.css").read_text(encoding="utf-8"))

    def test_ningun_estilo_pide_recursos_a_dominios_externos(self):
        for archivo in Path(settings.BASE_DIR, "static", "css").glob("*.css"):
            css = archivo.read_text(encoding="utf-8")
            self.assertNotIn("@import", css, archivo.name)
            self.assertIsNone(re.search(r"url\(\s*[\"']?(https?:)?//", css), archivo.name)
            self.assertIsNone(RECURSOS_EXTERNOS.search(css), archivo.name)

    def test_ninguna_plantilla_enlaza_hojas_o_fuentes_externas(self):
        for archivo in Path(settings.BASE_DIR, "templates").rglob("*.html"):
            html = archivo.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"<link[^>]+href=[\"']https?://", html), archivo.name)
            self.assertIsNone(RECURSOS_EXTERNOS.search(html), archivo.name)

    def test_las_paginas_precargan_la_fuente_propia_y_no_piden_nada_externo(self):
        for ruta in ("/", "/acceso/", "/registro/"):
            html = self.client.get(ruta, follow=True).content.decode()
            self.assertIn('rel="preload"', html, ruta)
            self.assertIn("/static/fonts/inter-latin-wght-normal.woff2", html, ruta)
            self.assertIn("crossorigin", html, ruta)
            self.assertIsNone(RECURSOS_EXTERNOS.search(html), ruta)
            for destino in re.findall(r"<(?:link|script|img)[^>]+(?:href|src)=[\"'](https?://[^\"']+)", html):
                self.fail(f"{ruta} pide un recurso externo: {destino}")
