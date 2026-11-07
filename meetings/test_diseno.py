"""Pruebas del diseno (TR-42): tema claro y oscuro, barra lateral y que las rutas sigan respondiendo igual."""
from django.contrib.staticfiles import finders
from django.urls import reverse

from .links import make_approval_token, make_token
from .models import SchedulingRule
from .test_approval import ApprovalBase

BARRA = 'id="barra"'
TEMA_JS = "js/tema.js"


class RutasSiguenIgualTests(ApprovalBase):
    """Las rutas existentes responden con el mismo codigo que antes del cambio de diseno."""

    def test_la_raiz_con_sesion_sigue_llevando_al_panel(self):
        self.login(self.asis)
        r = self.client.get("/")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], reverse("panel"))

    def test_la_raiz_sin_sesion_muestra_la_landing(self):
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_el_panel_sin_sesion_lleva_al_ingreso(self):
        r = self.client.get(reverse("panel"))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith(reverse("login")))

    def test_las_paginas_del_panel_responden_200_con_sesion(self):
        regla = SchedulingRule.objects.create(executive=self.ejec, created_by=self.ejec, weekday=4, start_hour=0, end_hour=24)
        for usuario in (self.asis, self.ejec):
            self.login(usuario)
            for url in (reverse("panel"), reverse("request_list"), reverse("request_detail", args=[self.req.pk]),
                        reverse("rules"), reverse("edit_rule", args=[regla.pk])):
                with self.subTest(usuario=usuario.full_name, url=url):
                    self.assertEqual(self.client.get(url).status_code, 200)

    def test_las_paginas_publicas_responden_igual(self):
        self.assertEqual(self.client.get(reverse("login")).status_code, 200)
        self.assertEqual(self.client.get(reverse("signup")).status_code, 200)
        self.assertEqual(self.client.get(reverse("public_availability", args=[make_token(self.req.pk)])).status_code, 200)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.get(reverse("public_approval", args=["no-valido"])).status_code, 404)


class TemaTests(ApprovalBase):
    def test_el_script_del_tema_existe(self):
        self.assertIsNotNone(finders.find(TEMA_JS))

    def test_el_script_del_tema_se_carga_en_head_antes_que_los_estilos(self):
        html = self.client.get(reverse("login")).content.decode()
        head = html.split("</head>")[0]
        self.assertIn(TEMA_JS, head)
        self.assertLess(head.index(TEMA_JS), head.index("css/app.css"))
        self.assertNotIn("defer", head.split(TEMA_JS)[1].split(">")[0])

    def test_el_panel_tiene_el_selector_de_tema_con_tres_opciones(self):
        self.login(self.asis)
        r = self.client.get(reverse("panel"))
        for valor in ("claro", "oscuro", "sistema"):
            self.assertContains(r, f'name="tema" value="{valor}"')
        self.assertContains(r, "<legend>Tema</legend>", html=False)

    def test_los_estilos_definen_el_tema_oscuro(self):
        with open(finders.find("css/app.css"), encoding="utf-8") as f:
            css = f.read()
        self.assertIn(':root[data-theme="dark"]', css)
        self.assertIn("prefers-color-scheme: dark", css)


class BarraLateralTests(ApprovalBase):
    def test_el_panel_muestra_las_tres_secciones_y_no_ajustes(self):
        self.login(self.asis)
        r = self.client.get(reverse("panel"))
        self.assertContains(r, BARRA)
        self.assertContains(r, ">Solicitudes<")
        self.assertContains(r, ">Vinculación<")
        self.assertContains(r, ">Reglas<")
        self.assertNotContains(r, "Ajustes")

    def test_marca_la_seccion_actual(self):
        self.login(self.asis)
        panel = self.client.get(reverse("panel")).content.decode()
        self.assertIn('title="Solicitudes" aria-current="page"', panel)
        reglas = self.client.get(reverse("rules")).content.decode()
        self.assertIn('title="Reglas" aria-current="page"', reglas)
        self.assertNotIn('title="Solicitudes" aria-current="page"', reglas)

    def test_el_detalle_y_las_reglas_usan_la_barra(self):
        self.login(self.ejec)
        self.assertContains(self.client.get(reverse("request_detail", args=[self.req.pk])), BARRA)
        self.assertContains(self.client.get(reverse("rules")), BARRA)

    def test_el_menu_de_usuario_muestra_nombre_rol_y_salir_con_csrf(self):
        self.login(self.asis)
        html = self.client.get(reverse("panel")).content.decode()
        menu = html.split('id="menu-usuario"')[1].split("</details>")[0]
        self.assertIn("Ana Asistente", menu)
        self.assertIn("Asistente", menu)
        self.assertIn(f'action="{reverse("logout")}"', menu)
        self.assertIn("csrfmiddlewaretoken", menu)

    def test_los_botones_de_la_barra_tienen_nombre_accesible(self):
        self.login(self.asis)
        r = self.client.get(reverse("panel"))
        self.assertContains(r, 'id="barra-contraer" aria-controls="barra-nav" aria-expanded="true" aria-label="Contraer menú"')
        self.assertContains(r, 'id="barra-menu" aria-controls="barra-contenido" aria-expanded="false">Menú<')
        self.assertContains(r, 'href="#contenido">Saltar al contenido<')

    def test_las_paginas_publicas_y_el_ingreso_no_llevan_barra(self):
        for url in (reverse("login"), reverse("public_availability", args=[make_token(self.req.pk)]), self.url):
            with self.subTest(url=url):
                r = self.client.get(url)
                self.assertNotContains(r, BARRA)
                self.assertContains(r, TEMA_JS)

    def test_la_lista_que_se_recarga_sola_no_trae_la_barra(self):
        self.login(self.asis)
        r = self.client.get(reverse("request_list"))
        self.assertNotContains(r, BARRA)
        self.assertNotContains(r, "<html")
        self.assertContains(r, "Revisión trimestral")


class PanelOrdenadoTests(ApprovalBase):
    def test_la_asistente_ve_nueva_solicitud_plegada(self):
        self.login(self.asis)
        r = self.client.get(reverse("panel"))
        self.assertContains(r, '<details class="card plegable" id="nueva-solicitud">')
        self.assertContains(r, "Nueva solicitud de reunión</summary>")

    def test_con_errores_el_formulario_se_muestra_abierto(self):
        self.login(self.asis)
        r = self.client.post(reverse("create_request"), {"executive": self.ejec.pk, "title": "", "counterpart_name": "",
                                                         "duration_min": 45})
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, 'id="nueva-solicitud" open', status_code=400)

    def test_el_ejecutivo_ve_su_codigo_en_vinculacion_y_no_el_formulario(self):
        self.login(self.ejec)
        r = self.client.get(reverse("panel"))
        self.assertContains(r, 'id="vinculacion"')
        self.assertContains(r, self.ejec.link_code)
        self.assertNotContains(r, 'id="nueva-solicitud"')

    def test_la_asistente_sin_vinculo_ve_como_vincularse(self):
        self.login(self.otra)
        r = self.client.get(reverse("panel"))
        self.assertContains(r, "Vincúlate con un ejecutivo para poder crear solicitudes.")
        self.assertContains(r, 'for="codigo-vinculo"')
        self.assertNotContains(r, 'id="nueva-solicitud"')

    def test_lista_vacia_muestra_ayuda_segun_el_rol(self):
        self.login(self.otra)
        r = self.client.get(reverse("request_list"))
        self.assertContains(r, "Aún no hay solicitudes de reunión.")
        self.assertContains(r, "Crear la primera solicitud")
        self.req.delete()
        self.login(self.ejec)
        r = self.client.get(reverse("request_list"))
        self.assertContains(r, "Cuando tu asistente cree una solicitud")
        self.assertNotContains(r, "Crear la primera solicitud")


class AprobacionSinCambiosTests(ApprovalBase):
    """La pagina publica de aprobacion conserva su contenido y su formulario protegido."""

    def test_conserva_las_tres_opciones_y_el_csrf(self):
        r = self.client.get(reverse("public_approval", args=[make_approval_token(self.req.pk)]))
        self.assertContains(r, "Aprobar esta opción", count=3)
        self.assertContains(r, "Ninguna me sirve")
        self.assertContains(r, "csrfmiddlewaretoken")


class IngresoTests(ApprovalBase):
    """Ingreso y registro con cuadro central: mismo funcionamiento, nuevo aspecto."""

    def test_ingreso_y_registro_muestran_el_cuadro_con_csrf(self):
        for url, enlace in ((reverse("login"), reverse("signup")), (reverse("signup"), reverse("login"))):
            with self.subTest(url=url):
                r = self.client.get(url)
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, '<body class="acceso"')
                self.assertContains(r, 'class="card acceso-card"')
                self.assertContains(r, "csrfmiddlewaretoken")
                self.assertContains(r, f'href="{enlace}"')
                self.assertNotContains(r, BARRA)

    def test_el_ingreso_sigue_funcionando_y_lleva_al_panel(self):
        r = self.client.post(reverse("login"), {"username": "ana@x.com", "password": "Secreto-12345"})
        self.assertRedirects(r, reverse("panel"), fetch_redirect_response=False)

    def test_las_demas_paginas_no_usan_el_fondo_de_ingreso(self):
        self.assertNotContains(self.client.get(self.url), 'class="acceso"')
