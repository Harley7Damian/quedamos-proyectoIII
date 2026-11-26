"""Pruebas de Mi perfil: datos, antelación de avisos, teléfono y cambio de contraseña."""
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .forms import normalizar_telefono
from .models import Profile, User

PW = "Secreto-12345"


def mk(email, name, role):
    return User.objects.create_user(username=email, email=email, password=PW, full_name=name, role=role)


class NormalizarTelefonoTests(SimpleTestCase):
    def test_acepta_formatos_comunes_y_los_lleva_a_formato_internacional(self):
        casos = {
            "+51 999 999 999": "+51999999999",
            "(+51) 999 999 999": "+51999999999",
            "+51-999-999-999": "+51999999999",
            "+1 (415) 555-0132": "+14155550132",
            "": "",
            "   ": "",
        }
        for crudo, esperado in casos.items():
            with self.subTest(crudo=crudo):
                self.assertEqual(normalizar_telefono(crudo), esperado)

    def test_rechaza_lo_que_no_es_un_numero_utilizable(self):
        for crudo in ("hola", "12345", "999999999", "999-999-999", "+51 99a 999 999", "0051999999999", "+0 999", "+51+999999999", "888888888", "+1234567890123456"):
            with self.subTest(crudo=crudo):
                with self.assertRaises(ValueError):
                    normalizar_telefono(crudo)


class PerfilBase(TestCase):
    def setUp(self):
        self.user = mk("carla@x.com", "Carla Ejecutiva", "ejecutivo")
        self.assertTrue(self.client.login(username=self.user.username, password=PW))

    def profile(self):
        return Profile.objects.get(user=self.user)

    def post_avisos(self, avisos, telefono=""):
        return self.client.post(reverse("perfil"), {"accion": "avisos", "avisos": avisos, "telefono": telefono})


class PerfilTests(PerfilBase):
    def test_exige_sesion(self):
        self.client.logout()
        r = self.client.get(reverse("perfil"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("login"), r["Location"])

    def test_muestra_cuenta_avisos_y_seguridad(self):
        html = self.client.get(reverse("perfil")).content.decode()
        for texto in ("carla@x.com", "Ejecutivo", "Código de vinculación", self.user.link_code, "Avisos de reunión",
                      "2 días antes", "5 minutos antes", "Cambiar contraseña"):
            with self.subTest(texto=texto):
                self.assertIn(texto, html)

    def test_por_defecto_estan_marcados_30_y_5_minutos(self):
        r = self.client.get(reverse("perfil"))
        marcados = r.context["avisos_form"]["avisos"].value()
        self.assertEqual(sorted(marcados), ["30", "5"])

    def test_la_asistente_no_ve_codigo_de_vinculacion(self):
        self.client.logout()
        mk("ana@x.com", "Ana Asistente", "asistente")
        self.client.login(username="ana@x.com", password=PW)
        self.assertNotIn("Código de vinculación", self.client.get(reverse("perfil")).content.decode())

    def test_el_menu_de_usuario_enlaza_al_perfil(self):
        self.assertContains(self.client.get(reverse("panel")), f'href="{reverse("perfil")}"')

    def test_guarda_nombre_y_area(self):
        r = self.client.post(reverse("perfil"), {"accion": "datos", "full_name": "  Carla   Mendoza ", "area": "finanzas"})
        self.assertRedirects(r, reverse("perfil"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, "Carla Mendoza")
        self.assertEqual(self.profile().area, "finanzas")

    def test_rechaza_un_nombre_demasiado_corto(self):
        r = self.client.post(reverse("perfil"), {"accion": "datos", "full_name": "A", "area": ""})
        self.assertEqual(r.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, "Carla Ejecutiva")

    def test_no_permite_cambiar_correo_ni_rol_desde_el_perfil(self):
        self.client.post(reverse("perfil"), {"accion": "datos", "full_name": "Carla", "area": "", "email": "otro@x.com", "role": "asistente"})
        self.user.refresh_from_db()
        self.assertEqual((self.user.username, self.user.role), ("carla@x.com", "ejecutivo"))


class AvisosEnPerfilTests(PerfilBase):
    def test_guarda_la_antelacion_elegida_ordenada(self):
        r = self.post_avisos(["5", "2880", "60"])
        self.assertRedirects(r, reverse("perfil"))
        self.assertEqual(self.profile().avisos_minutos, [2880, 60, 5])

    def test_guarda_el_telefono_en_formato_internacional(self):
        self.post_avisos(["30"], "+51 999 999 999")
        self.assertEqual(self.profile().telefono, "+51999999999")

    def test_un_telefono_invalido_no_guarda_nada(self):
        r = self.post_avisos(["1440"], "12345")
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, "código del país", status_code=400)
        p = self.profile()
        self.assertEqual((p.telefono, p.avisos_efectivos), ("", [30, 5]))

    def test_vaciar_el_telefono_apaga_las_llamadas(self):
        self.post_avisos(["30"], "+51999999999")
        self.post_avisos(["30"], "")
        self.assertEqual(self.profile().telefono, "")

    def test_exige_al_menos_un_aviso(self):
        r = self.client.post(reverse("perfil"), {"accion": "avisos", "telefono": ""})
        self.assertContains(r, "Elige al menos un aviso.", status_code=400)

    def test_limita_a_cuatro_avisos(self):
        r = self.post_avisos(["2880", "1440", "120", "60", "30"])
        self.assertContains(r, "como máximo 4", status_code=400)

    def test_ignora_valores_que_no_son_opciones(self):
        r = self.post_avisos(["7"])
        self.assertEqual(r.status_code, 400)

    def test_el_endpoint_antiguo_del_telefono_tambien_valida(self):
        self.client.post(reverse("guardar_telefono"), {"telefono": "no es un número"})
        self.assertEqual(self.profile().telefono, "")
        self.client.post(reverse("guardar_telefono"), {"telefono": "+51 987 654 321"})
        self.assertEqual(self.profile().telefono, "+51987654321")


class CambiarClaveTests(PerfilBase):
    def test_cambia_la_clave_y_mantiene_la_sesion(self):
        r = self.client.post(reverse("cambiar_clave"), {"old_password": PW, "new_password1": "Otra-clave-2026", "new_password2": "Otra-clave-2026"})
        self.assertRedirects(r, reverse("perfil"))
        self.assertEqual(self.client.get(reverse("perfil")).status_code, 200)  # sigue con sesión
        self.client.logout()
        self.assertTrue(self.client.login(username="carla@x.com", password="Otra-clave-2026"))

    def test_rechaza_la_clave_actual_incorrecta(self):
        r = self.client.post(reverse("cambiar_clave"), {"old_password": "mala", "new_password1": "Otra-clave-2026", "new_password2": "Otra-clave-2026"})
        self.assertEqual(r.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PW))

    def test_rechaza_una_clave_debil(self):
        r = self.client.post(reverse("cambiar_clave"), {"old_password": PW, "new_password1": "12345678", "new_password2": "12345678"})
        self.assertEqual(r.status_code, 400)

    def test_exige_sesion(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("cambiar_clave")).status_code, 302)
