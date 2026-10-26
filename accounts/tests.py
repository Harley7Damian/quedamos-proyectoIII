import re

from django.test import TestCase
from django.urls import reverse

from .models import User


def signup(client, email="ana@x.com", name="Ana Asistente", role="asistente", pw="Secreto-12345"):
    return client.post(reverse("signup"), {"full_name": name, "email": email, "role": role, "password1": pw, "password2": pw})


class SignupTests(TestCase):
    def test_registro_crea_usuario_con_rol_y_entra_al_panel(self):
        r = signup(self.client)
        self.assertRedirects(r, reverse("panel"))
        u = User.objects.get(username="ana@x.com")
        self.assertEqual((u.full_name, u.role), ("Ana Asistente", "asistente"))

    def test_solo_el_ejecutivo_recibe_codigo_de_6_caracteres(self):
        signup(self.client, "carla@x.com", "Carla", "ejecutivo")
        self.client.logout()
        signup(self.client, "ana@x.com", "Ana", "asistente")
        self.assertRegex(User.objects.get(username="carla@x.com").link_code, r"^[A-HJ-NP-Z2-9]{6}$")
        self.assertIsNone(User.objects.get(username="ana@x.com").link_code)

    def test_un_rol_invalido_es_rechazado(self):
        r = signup(self.client, role="admin")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="ana@x.com").exists())

    def test_correo_repetido_o_con_mayusculas_es_rechazado(self):
        signup(self.client)
        self.client.logout()
        r = signup(self.client, email="ANA@x.com")
        self.assertContains(r, "Ya existe una cuenta con ese correo")
        self.assertEqual(User.objects.count(), 1)

    def test_contrasena_debil_es_rechazada(self):
        r = signup(self.client, pw="12345678")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(User.objects.count(), 0)

    def test_los_codigos_no_se_repiten(self):
        codes = {User.objects.create_user(username=f"e{i}@x.com", password="x", role="ejecutivo", full_name=f"E{i}").link_code for i in range(60)}
        self.assertEqual(len(codes), 60)

    def test_el_codigo_no_cambia_al_guardar_de_nuevo(self):
        u = User.objects.create_user(username="e@x.com", password="x", role="ejecutivo", full_name="Ejec")
        first = u.link_code
        u.full_name = "Otro nombre"
        u.save()
        u.refresh_from_db()
        self.assertEqual(u.link_code, first)


class LoginTests(TestCase):
    def setUp(self):
        signup(self.client)
        self.client.logout()

    def test_ingreso_con_correo_en_cualquier_capitalizacion(self):
        r = self.client.post(reverse("login"), {"username": " ANA@x.com ", "password": "Secreto-12345"})
        self.assertRedirects(r, reverse("panel"))

    def test_credenciales_incorrectas(self):
        r = self.client.post(reverse("login"), {"username": "ana@x.com", "password": "mala"})
        self.assertContains(r, "Correo o contraseña incorrectos")

    def test_panel_exige_sesion(self):
        r = self.client.get(reverse("panel"))
        self.assertRedirects(r, f"{reverse('login')}?next={reverse('panel')}")

    def test_salir_cierra_la_sesion(self):
        self.client.post(reverse("login"), {"username": "ana@x.com", "password": "Secreto-12345"})
        self.client.post(reverse("logout"))
        self.assertEqual(self.client.get(reverse("panel")).status_code, 302)
