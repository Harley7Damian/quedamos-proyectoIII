"""Pruebas de la validación estricta de correos (registro y solicitudes)."""
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .correo import validar_correo
from .models import User

PW = "Secreto-12345"


class ValidarCorreoTests(SimpleTestCase):
    def test_acepta_correos_normales_y_los_deja_en_minusculas(self):
        casos = {
            "  Ana.Perez@Empresa.COM ": "ana.perez@empresa.com",
            "pedro+ventas@logistica-andina.com.pe": "pedro+ventas@logistica-andina.com.pe",
            "a_b-c@usil.edu.pe": "a_b-c@usil.edu.pe",
            "carla@x.com": "carla@x.com",
        }
        for crudo, esperado in casos.items():
            with self.subTest(crudo=crudo):
                self.assertEqual(validar_correo(crudo), esperado)

    def test_vacio_es_valido_porque_el_campo_es_opcional(self):
        self.assertEqual(validar_correo(""), "")
        self.assertEqual(validar_correo("   "), "")

    def test_rechaza_formatos_rotos(self):
        for crudo in ("sinarroba.com", "dos@@x.com", "a@b", "a@localhost", "a@.com", "a@x..com", "@x.com",
                      ".a@x.com", "a.@x.com", "a..b@x.com", "a b@x.com", "a@-x.com", "a@x.c", "a@x.123",
                      "a@" + "x" * 64 + ".com", "ñandú@x.com"):
            with self.subTest(crudo=crudo):
                with self.assertRaises(ValidationError):
                    validar_correo(crudo)

    def test_detecta_errores_de_tipeo_comunes_y_sugiere_la_correccion(self):
        casos = {
            "ana@gmial.com": "ana@gmail.com",
            "ana@gmail.con": "ana@gmail.com",
            "ana@hotmial.com": "ana@hotmail.com",
            "ana@outlok.com": "ana@outlook.com",
            "ana@empresa.con": "ana@empresa.com",
            "ana@empresa.coom": "ana@empresa.com",
            "ana@usil.edu.p": "ana@usil.edu.pe",
        }
        for crudo, sugerido in casos.items():
            with self.subTest(crudo=crudo):
                with self.assertRaises(ValidationError) as ctx:
                    validar_correo(crudo)
                self.assertIn(f"¿Quisiste decir {sugerido}?", ctx.exception.messages[0])

    def test_no_rechaza_dominios_reales_parecidos_a_los_comunes(self):
        for correcto in ("ana@outlook.es", "ana@gmail.com", "ana@yahoo.es", "ana@icloud.com", "ana@hotmail.es", "ana@empresa.co"):
            with self.subTest(correcto=correcto):
                self.assertEqual(validar_correo(correcto), correcto)


class CorreoEnRegistroTests(TestCase):
    def registrar(self, email):
        return self.client.post(reverse("signup"), {"full_name": "Ana Asistente", "email": email, "role": "asistente",
                                                    "password1": PW, "password2": PW})

    def test_el_registro_rechaza_un_dominio_con_error_de_tipeo(self):
        r = self.registrar("ana@gmial.com")
        self.assertContains(r, "¿Quisiste decir ana@gmail.com?")
        self.assertFalse(User.objects.filter(username="ana@gmial.com").exists())

    def test_el_registro_guarda_el_correo_limpio(self):
        self.registrar("  Ana@Empresa.com ")
        self.assertTrue(User.objects.filter(username="ana@empresa.com").exists())

    def test_el_registro_sigue_rechazando_un_correo_repetido(self):
        self.registrar("ana@empresa.com")
        self.client.logout()
        self.assertContains(self.registrar("ANA@empresa.com"), "Ya existe una cuenta")


class CorreoEnSolicitudTests(TestCase):
    def setUp(self):
        from meetings.models import AssistantLink
        self.ejec = User.objects.create_user(username="carla@x.com", email="carla@x.com", password=PW, full_name="Carla", role="ejecutivo")
        self.asis = User.objects.create_user(username="ana@x.com", email="ana@x.com", password=PW, full_name="Ana", role="asistente")
        AssistantLink.objects.create(assistant=self.asis, executive=self.ejec)
        self.client.login(username="ana@x.com", password=PW)

    def crear(self, correo):
        return self.client.post(reverse("create_request"), {
            "executive": self.ejec.pk, "title": "Revisión", "counterpart_name": "Pedro Gómez",
            "counterpart_email": correo, "duration_min": 30, "notes": "",
        })

    def test_la_solicitud_rechaza_el_error_de_tipeo_con_sugerencia(self):
        r = self.crear("pedro@empresa.con")
        self.assertContains(r, "¿Quisiste decir pedro@empresa.com?", status_code=400)

    def test_el_correo_de_la_contraparte_sigue_siendo_opcional(self):
        self.assertEqual(self.crear("").status_code, 302)

    def test_guarda_el_correo_en_minusculas(self):
        from meetings.models import MeetingRequest
        self.crear(" Pedro@Empresa.com ")
        self.assertEqual(MeetingRequest.objects.get().counterpart_email, "pedro@empresa.com")
