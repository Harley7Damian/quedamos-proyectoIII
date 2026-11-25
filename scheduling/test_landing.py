"""Pruebas de la landing publica (TR-44 y TR-45): contenido, pestañas, planes informativos y redireccion con sesion."""
import re

from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .mock import MOCK_PROPOSAL

PW = "Secreto-12345"


def leer(ruta_estatica):
    with open(finders.find(ruta_estatica), encoding="utf-8") as archivo:
        return archivo.read()


class LandingTests(TestCase):
    def setUp(self):
        self.url = reverse("landing")

    def html(self):
        return self.client.get(self.url).content.decode()

    def test_la_raiz_es_la_landing(self):
        self.assertEqual(self.url, "/")

    def test_responde_200_sin_sesion(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "landing.html")

    def test_muestra_la_propuesta_de_valor_y_los_tres_pasos(self):
        r = self.client.get(self.url)
        self.assertContains(r, "Coordina reuniones de ejecutivos")
        self.assertContains(r, "sin intercambiar correos")
        self.assertContains(r, "Cómo funciona en tres pasos")
        for paso in ("Se registra la solicitud", "Quedamos propone tres horarios", "El ejecutivo aprueba con un toque"):
            self.assertContains(r, paso)

    def test_muestra_la_demostracion_de_la_tarjeta_con_datos_ficticios(self):
        r = self.client.get(self.url)
        self.assertContains(r, MOCK_PROPOSAL.title)
        for slot in MOCK_PROPOSAL.slots:
            self.assertContains(r, slot.reason)
        self.assertContains(r, "Ejemplo con datos ficticios")
        self.assertContains(r, reverse("demo_card"))

    def test_muestra_la_seccion_de_confianza_corporativa(self):
        r = self.client.get(self.url)
        for titulo in ("Enlaces firmados", "Horarios protegidos", "Cada persona ve lo suyo"):
            self.assertContains(r, titulo)

    def test_muestra_los_tres_planes_con_su_precio_definido(self):
        r = self.client.get(self.url)
        for plan in ("Gratis", "Profesional", "Empresa"):
            self.assertContains(r, f'<h3 id="plan-{plan.lower()}">{plan}</h3>', html=True)
        self.assertNotContains(r, "Por definir")
        self.assertContains(r, "S/ 0")
        self.assertContains(r, "S/ 52")
        self.assertNotContains(r, "S/ 39")
        self.assertContains(r, "por ejecutivo al mes")
        self.assertContains(r, "A medida")
        self.assertContains(r, "desde 5 ejecutivos")

    def test_el_plan_gratis_limita_el_volumen_y_el_profesional_lo_quita(self):
        r = self.client.get(self.url)
        self.assertContains(r, "Hasta 5 solicitudes de reunión al mes")
        self.assertContains(r, "Solicitudes de reunión sin límite mensual")
        self.assertContains(r, "Durante el piloto todas las funciones están habilitadas")

    def test_los_botones_dicen_crear_cuenta_de_prueba_y_no_hay_cobros(self):
        r = self.client.get(self.url)
        self.assertContains(r, "Crear cuenta de prueba", count=5)  # hero, tres planes y cierre
        self.assertNotContains(r, "Solicitar acceso piloto")
        self.assertContains(r, "No se realiza ningún cobro")
        self.assertNotContains(r, "<form")
        self.assertNotContains(r, "$")

    def test_los_botones_llevan_al_registro_y_hay_enlace_para_ingresar(self):
        r = self.client.get(self.url)
        self.assertContains(r, f'href="{reverse("signup")}"', count=6)  # cabecera + los cinco botones
        self.assertContains(r, f'href="{reverse("login")}"')

    def test_tiene_preguntas_frecuentes_y_un_pie_de_pagina_con_enlaces(self):
        r = self.client.get(self.url)
        self.assertContains(r, 'id="preguntas"')
        self.assertContains(r, "¿La contraparte necesita crear una cuenta?")
        for etiqueta in ("Producto", "Comparar", "Tu cuenta"):
            self.assertContains(r, f'<nav aria-label="{etiqueta}">')
        self.assertContains(r, reverse("health"))
        self.assertNotContains(r, '<nav aria-label="Recursos">')

    def test_el_pie_enlaza_el_repositorio_y_no_tiene_enlaces_vacios(self):
        r = self.client.get(self.url)
        self.assertContains(r, 'aria-label="Enlaces de Quedamos"')
        self.assertContains(r, "https://github.com/Harley7Damian/quedamos-proyectoIII")
        self.assertNotContains(r, 'href="#"')

    def test_la_comparativa_es_una_tabla_accesible_y_declara_lo_que_falta(self):
        r = self.client.get(self.url)
        self.assertContains(r, 'id="comparacion"')
        self.assertContains(r, '<th scope="col" class="col-quedamos">', html=False)
        for fila in ("Cruza la disponibilidad de ambas partes", "Propone horarios y explica el motivo de cada uno", "Conexión con Google Calendar u Outlook"):
            self.assertContains(r, fila)
        self.assertContains(r, "Todavía no")
        self.assertContains(r, "no entre marcas")

    def test_las_tarjetas_de_confianza_y_pasos_tienen_icono_o_numero(self):
        html = self.html()
        self.assertEqual(html.count('class="icono-tarjeta"'), 3)
        self.assertGreaterEqual(html.count('class="card tarjeta'), 6)

    def test_la_cabecera_enlaza_las_secciones(self):
        html = self.html()
        for ancla in ("#funciones", "#comparacion", "#planes"):
            self.assertIn(f'href="{ancla}"', html)
        for identificador in ("funciones", "planes", "como-funciona"):
            self.assertIn(f'id="{identificador}"', html)

    def test_la_marca_lleva_a_la_landing_sin_sesion(self):
        self.assertContains(self.client.get(reverse("login")), 'class="brand" href="/"')

    def test_con_sesion_pasa_directo_al_panel(self):
        User.objects.create_user(username="a@x.com", email="a@x.com", password=PW, full_name="Ana", role="asistente")
        self.client.login(username="a@x.com", password=PW)
        r = self.client.get(self.url)
        self.assertRedirects(r, reverse("panel"), fetch_redirect_response=False)

    def test_solo_acepta_lectura(self):
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_la_demostracion_sigue_disponible(self):
        self.assertEqual(self.client.get(reverse("demo_card")).status_code, 200)


class PestanasTests(TestCase):
    def setUp(self):
        self.html = self.client.get(reverse("landing")).content.decode()

    def test_hay_cuatro_pestanas_y_cuatro_paneles_con_roles_aria(self):
        self.assertEqual(self.html.count('role="tablist"'), 1)
        self.assertEqual(self.html.count('role="tab"'), 4)
        self.assertEqual(self.html.count('role="tabpanel"'), 4)

    def test_cada_pestana_controla_un_panel_que_existe_y_viceversa(self):
        for control in re.findall(r'aria-controls="([^"]+)"', self.html):
            self.assertIn(f'id="{control}"', self.html)
        for panel, pestana in re.findall(r'id="(panel-[^"]+)" aria-labelledby="([^"]+)"', self.html):
            self.assertIn(f'id="{pestana}"', self.html)
            self.assertIn(f'aria-controls="{panel}"', self.html)

    def test_solo_la_primera_pestana_arranca_seleccionada(self):
        self.assertEqual(self.html.count('aria-selected="true"'), 1)
        self.assertEqual(self.html.count('aria-selected="false"'), 3)

    def test_las_pestanas_tienen_los_nombres_esperados(self):
        for nombre in ("Solicitud", "Disponibilidad", "Tres horarios", "Aprobación en un toque"):
            self.assertIn(f"<span>{nombre}</span>", self.html)

    def test_sin_javascript_los_paneles_no_estan_ocultos(self):
        self.assertNotIn("hidden", re.findall(r'<div class="panel"[^>]*>', self.html)[0])
        self.assertEqual(len(re.findall(r'<div class="panel" role="tabpanel"[^>]*>', self.html)), 4)

    def test_las_maquetas_son_decorativas_para_lectores_de_pantalla(self):
        self.assertGreaterEqual(self.html.count('class="mock" aria-hidden="true"'), 3)


class RecursosYMovimientoTests(TestCase):
    def setUp(self):
        self.html = self.client.get(reverse("landing")).content.decode()

    def test_existen_los_estilos_y_el_script_y_la_pagina_los_carga(self):
        self.assertIsNotNone(finders.find("css/landing.css"))
        self.assertIsNotNone(finders.find("js/landing.js"))
        self.assertIn("css/landing.css", self.html)
        self.assertIn("js/landing.js", self.html)

    def test_no_depende_de_recursos_externos(self):
        # Ningun recurso (scripts, estilos, imagenes) se carga desde otro sitio; los enlaces de navegacion, como el del repositorio, si pueden salir.
        self.assertIsNone(re.search(r'(?:src="|<link[^>]*href=")(?:https?:)?//', self.html))
        self.assertNotIn("<iframe", self.html)

    def test_no_hay_scripts_en_linea(self):
        for etiqueta in re.findall(r"<script[^>]*>", self.html, flags=re.IGNORECASE):
            self.assertIn("src=", etiqueta)

    def test_el_script_y_los_estilos_respetan_reducir_movimiento(self):
        self.assertIn("prefers-reduced-motion", leer("js/landing.js"))
        self.assertIn("prefers-reduced-motion", leer("css/landing.css"))

    def test_la_rotacion_automatica_se_pausa_y_se_detiene_con_la_persona(self):
        js = leer("js/landing.js")
        for evento in ("mouseenter", "focusin", "ArrowRight", "Home", "End"):
            self.assertIn(evento, js)

    def test_las_pestanas_rotan_cada_seis_segundos(self):
        self.assertIn("CICLO = 6000", leer("js/landing.js"))
        self.assertIn("6s linear", leer("css/landing.css"))


class PaletaYTemaTests(TestCase):
    def test_la_paleta_extendida_existe_en_tema_claro_y_oscuro(self):
        css = leer("css/app.css")
        for variable in ("--accent:", "--amber:", "--rose:", "--grad-1:"):
            self.assertGreaterEqual(css.count(variable), 3, variable)  # claro, oscuro y respaldo sin JavaScript

    def test_la_primera_visita_usa_el_tema_claro(self):
        js = leer("js/tema.js")
        self.assertIn("? valor : 'claro'", js)
        self.assertIn("'sistema'", js)  # sigue siendo una opcion elegible
