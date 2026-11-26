"""Pruebas de las herramientas de administración de cuentas (superusuario)."""
from django.test import TestCase
from django.urls import reverse

from .models import User

PW = "Secreto-12345"


class AdminCuentasTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin@quedamos.pe", "admin@quedamos.pe", PW, full_name="Administración")
        self.error = User.objects.create_user("error@empresa.com", "error@empresa.com", PW, full_name="Cuenta por error")
        self.client.force_login(self.admin)

    def test_listado_con_busqueda_y_filtro_de_activos(self):
        r = self.client.get(reverse("admin:accounts_user_changelist"), {"q": "error@empresa", "is_active__exact": "1"})
        self.assertContains(r, "error@empresa.com")
        self.assertNotContains(r, "admin@quedamos.pe</a>")

    def test_desactivar_y_reactivar_cuentas(self):
        url = reverse("admin:accounts_user_changelist")
        self.client.post(url, {"action": "desactivar_cuentas", "_selected_action": [self.error.pk]})
        self.error.refresh_from_db()
        self.assertFalse(self.error.is_active)
        self.client.post(url, {"action": "reactivar_cuentas", "_selected_action": [self.error.pk]})
        self.error.refresh_from_db()
        self.assertTrue(self.error.is_active)

    def test_no_permite_desactivar_la_propia_cuenta(self):
        r = self.client.post(reverse("admin:accounts_user_changelist"),
                             {"action": "desactivar_cuentas", "_selected_action": [self.admin.pk]}, follow=True)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertContains(r, "Tu propia cuenta no se desactiva")

    def test_una_cuenta_desactivada_no_ingresa_y_no_se_puede_registrar_de_nuevo(self):
        self.error.is_active = False
        self.error.save()
        self.client.logout()
        r = self.client.post(reverse("login"), {"username": "error@empresa.com", "password": PW})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(r.status_code, 200)
        r = self.client.post(reverse("signup"), {"full_name": "Otra", "email": "error@empresa.com", "role": "asistente",
                                                 "password1": PW, "password2": PW})
        self.assertContains(r, "Esa cuenta está desactivada")

    def test_al_guardar_desde_el_admin_el_usuario_queda_en_minusculas_y_con_el_correo_igual(self):
        r = self.client.post(reverse("admin:accounts_user_add"), {
            "username": "  Nueva.Persona@Empresa.com ", "password1": PW, "password2": PW,
            "full_name": "Nueva Persona", "role": "ejecutivo",
        })
        self.assertEqual(r.status_code, 302)
        nueva = User.objects.get(full_name="Nueva Persona")
        self.assertEqual(nueva.username, "nueva.persona@empresa.com")
        self.assertEqual(nueva.email, "nueva.persona@empresa.com")
        self.assertTrue(nueva.link_code)
