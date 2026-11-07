"""Pruebas de usabilidad de formularios (TR-46): ver contraseña, requisitos, copiar código y rol como etiqueta."""
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from .models import User

PW = "Secreto-12345"


def mk(email, name, role):
    return User.objects.create_user(username=email, email=email, password=PW, full_name=name, role=role)


class VerContrasenaTests(TestCase):
    def test_el_ingreso_tiene_el_boton_de_ojo_con_etiqueta_accesible(self):
        r = self.client.get(reverse("login"))
        self.assertContains(r, "data-ver-clave", count=1)
        self.assertContains(r, 'aria-label="Mostrar contraseña"')
        self.assertContains(r, 'aria-pressed="false"')

    def test_el_registro_tiene_un_ojo_por_cada_campo_de_contrasena(self):
        r = self.client.get(reverse("signup"))
        self.assertContains(r, "data-ver-clave", count=2)

    def test_el_boton_apunta_a_su_campo(self):
        r = self.client.get(reverse("signup"))
        self.assertContains(r, 'aria-controls="id_password1"')
        self.assertContains(r, 'aria-controls="id_password2"')

    def test_el_boton_arranca_oculto_para_quien_no_tiene_javascript(self):
        self.assertContains(self.client.get(reverse("login")), "data-ver-clave hidden")


class RequisitosTests(TestCase):
    def test_el_registro_lista_los_tres_requisitos_y_los_vincula_al_campo(self):
        r = self.client.get(reverse("signup"))
        for clave in ("largo", "numerica", "coincide"):
            self.assertContains(r, f'data-req="{clave}"')
        self.assertContains(r, 'aria-describedby="requisitos-clave"')
        self.assertContains(r, 'id="requisitos-clave"')

    def test_el_ingreso_no_muestra_requisitos(self):
        self.assertNotContains(self.client.get(reverse("login")), "data-requisitos")

    def test_el_servidor_sigue_validando_la_contrasena(self):
        datos = {"full_name": "Ana Pérez", "email": "ana@x.com", "role": "asistente", "password1": "12345678", "password2": "12345678"}
        r = self.client.post(reverse("signup"), datos)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="ana@x.com").exists())


class RecursosTests(TestCase):
    def test_existen_el_script_y_los_estilos(self):
        self.assertIsNotNone(finders.find("js/formularios.js"))
        self.assertIsNotNone(finders.find("css/formularios.css"))

    def test_las_paginas_cargan_script_y_estilos(self):
        r = self.client.get(reverse("login"))
        self.assertContains(r, "js/formularios.js")
        self.assertContains(r, "css/formularios.css")


class CopiarCodigoTests(TestCase):
    def test_el_ejecutivo_ve_el_boton_de_copiar_junto_a_su_codigo(self):
        ejec = mk("carla@x.com", "Carla Ejecutiva", "ejecutivo")
        self.client.login(username=ejec.username, password=PW)
        r = self.client.get(reverse("panel"))
        self.assertContains(r, 'data-copiar="#mycode"')
        self.assertContains(r, 'id="mycode"')
        self.assertContains(r, ejec.link_code)
        self.assertContains(r, 'role="status"')

    def test_la_asistente_no_ve_boton_de_copiar(self):
        asis = mk("ana@x.com", "Ana Asistente", "asistente")
        self.client.login(username=asis.username, password=PW)
        self.assertNotContains(self.client.get(reverse("panel")), "data-copiar")


class EtiquetaDeRolTests(TestCase):
    def ver(self, rol):
        usuario = mk(f"{rol}@x.com", f"Nombre {rol}", rol)
        self.client.login(username=usuario.username, password=PW)
        return self.client.get(reverse("panel")).content.decode()

    def test_el_ejecutivo_ve_su_rol_como_etiqueta_en_el_menu_y_en_el_encabezado(self):
        html = self.ver("ejecutivo")
        menu = html.split('id="menu-usuario"')[1].split("</details>")[0]
        self.assertIn('class="rol rol-ejecutivo">Ejecutivo', menu)
        self.assertIn("Vista de ejecutivo", html)

    def test_la_asistente_ve_su_rol_como_etiqueta_en_el_menu_y_en_el_encabezado(self):
        html = self.ver("asistente")
        menu = html.split('id="menu-usuario"')[1].split("</details>")[0]
        self.assertIn('class="rol rol-asistente">Asistente', menu)
        self.assertIn("Vista de asistente", html)

    def test_las_paginas_sin_barra_tambien_muestran_la_etiqueta(self):
        usuario = mk("ana@x.com", "Ana Asistente", "asistente")
        self.client.login(username=usuario.username, password=PW)
        r = self.client.get(reverse("onboarding"))
        self.assertContains(r, 'class="rol rol-asistente"')

    def test_los_estilos_distinguen_los_dos_roles(self):
        ruta = finders.find("css/formularios.css")
        with open(ruta, encoding="utf-8") as archivo:
            css = archivo.read()
        self.assertIn(".rol-ejecutivo", css)
        self.assertIn(".rol-asistente", css)
