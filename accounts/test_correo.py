"""Pruebas de la validación estricta de correos (registro y solicitudes)."""
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
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
        for correcto in ("ana.perez@outlook.es", "ana.perez@gmail.com", "ana.perez@yahoo.es", "ana.perez@icloud.com",
                         "ana.perez@hotmail.es", "ana@empresa.co", "ana@yahoo.co.jp".replace("ana", "anita")):
            with self.subTest(correcto=correcto):
                self.assertEqual(validar_correo(correcto), correcto)


class CorreoEstrictoTests(SimpleTestCase):
    def rechaza(self, crudo, fragmento):
        with self.assertRaises(ValidationError) as ctx:
            validar_correo(crudo)
        self.assertIn(fragmento, ctx.exception.messages[0], crudo)

    def test_reglas_de_gmail(self):
        self.rechaza("ana@gmail.com", "entre 6 y 30")
        self.rechaza("ana_perez@gmail.com", "solo admite letras, números y puntos")
        self.rechaza(".anaperez@gmail.com", "antes de la arroba no parece válida")
        self.rechaza("anaperez.+citas@gmail.com", "no puede empezar ni terminar con punto")
        self.rechaza("anita" * 7 + "@gmail.com", "entre 6 y 30")
        self.assertEqual(validar_correo("Ana.Perez+citas@Gmail.com"), "ana.perez+citas@gmail.com")

    def test_reglas_de_outlook_hotmail_yahoo_e_icloud(self):
        self.rechaza("987654321@hotmail.com", "incluir letras")
        self.rechaza("ana perez@outlook.com", "antes de la arroba")
        self.rechaza("ana!@outlook.com", "solo admite letras")
        self.rechaza("ana@yahoo.com", "entre 4 y 32")
        self.rechaza("1ana.perez@yahoo.com", "empieza con una letra")
        self.rechaza("ana.p.perez@yahoo.com", "un punto")
        self.rechaza("ab@icloud.com", "al menos 3")
        for bueno in ("ana-perez@outlook.com", "ana_perez@hotmail.com", "ana.perez@outlook.com.pe", "ana_perez@yahoo.com",
                      "ana.perez@live.com", "ana_perez@icloud.com", "ana.perez@proton.me"):
            with self.subTest(bueno=bueno):
                self.assertEqual(validar_correo(bueno), bueno)

    def test_dominios_con_nombre_de_proveedor_que_no_existen_se_corrigen(self):
        self.rechaza("anaperez@gmail.es", "¿Quisiste decir anaperez@gmail.com?")
        self.rechaza("anaperez@gmaiil.com", "¿Quisiste decir anaperez@gmail.com?")
        self.rechaza("anaperez@hotmal.com", "¿Quisiste decir anaperez@hotmail.com?")
        self.rechaza("anaperez@outlok.es", "¿Quisiste decir anaperez@outlook.com?")
        self.rechaza("anaperez@yahooo.es", "¿Quisiste decir anaperez@yahoo.com?")

    def test_dominios_institucionales(self):
        for bueno in ("ana@usil.edu.pe", "profesor@pucp.edu.pe", "ana@mail.usil.edu.pe", "juan.perez@upch.edu.pe",
                      "docente@unxx.edu.pe", "ana@minedu.gob.pe"):
            with self.subTest(bueno=bueno):
                self.assertEqual(validar_correo(bueno), bueno)
        self.rechaza("ana@usli.edu.pe", "¿Quisiste decir ana@usil.edu.pe?")
        self.rechaza("ana@pcup.edu.pe", "¿Quisiste decir ana@pucp.edu.pe?")
        self.rechaza("ana@edu.pe", "Falta el nombre de la empresa o institución")
        self.rechaza("ana@com.pe", "Falta el nombre de la empresa o institución")
        self.rechaza("ana@gob.pe", "Falta el nombre de la empresa o institución")

    def test_terminaciones_inexistentes(self):
        self.rechaza("ana@empresa.zzz", "terminación")
        self.rechaza("ana@empresa.qq", "terminación")
        self.assertEqual(validar_correo("ana@empresa.lat"), "ana@empresa.lat")
        self.assertEqual(validar_correo("ana@empresa.com.pe"), "ana@empresa.com.pe")

    def test_dominios_de_ejemplo_y_temporales(self):
        for malo in ("ana@example.com", "ana@test.com", "ana@empresa.test", "ana@dominio.com", "ana@localhost.invalid"):
            with self.subTest(malo=malo):
                self.rechaza(malo, "de ejemplo")
        for malo in ("ana@mailinator.com", "ana@yopmail.com", "ana@temp-mail.org", "ana@x.guerrillamail.com"):
            with self.subTest(malo=malo):
                self.rechaza(malo, "temporales")

    def test_nombres_de_usuario_de_prueba(self):
        for malo in ("a@empresa.com", "test@empresa.com", "asdf@empresa.com", "qwerty@empresa.com", "aaaa@empresa.com",
                     "prueba@empresa.com", "123456@empresa.com", "test+1@empresa.com"):
            with self.subTest(malo=malo):
                self.rechaza(malo, "parece de prueba")
        self.assertEqual(validar_correo("testa@empresa.com"), "testa@empresa.com")

    @override_settings(CORREO_VERIFICAR_DNS=True)
    def test_con_dns_activado_un_dominio_desconocido_debe_existir(self):
        with mock.patch("accounts.correo._dominio_existe", return_value=False) as consulta:
            self.rechaza("ana@empresa-inventada.com", "No encontramos el dominio empresa-inventada.com")
            consulta.assert_called_once_with("empresa-inventada.com")
        with mock.patch("accounts.correo._dominio_existe", return_value=True):
            self.assertEqual(validar_correo("ana@empresa-real.com"), "ana@empresa-real.com")

    @override_settings(CORREO_VERIFICAR_DNS=True)
    def test_con_dns_activado_no_se_consulta_por_proveedores_ni_instituciones_conocidas(self):
        with mock.patch("accounts.correo._dominio_existe", return_value=False) as consulta:
            validar_correo("anaperez@gmail.com")
            validar_correo("ana@usil.edu.pe")
            consulta.assert_not_called()

    @override_settings(CORREO_VERIFICAR_DNS=False)
    def test_sin_dns_no_se_consulta_la_red(self):
        with mock.patch("accounts.correo._dominio_existe") as consulta:
            validar_correo("ana@empresa-inventada.com")
            consulta.assert_not_called()


class ExistenciaDelDominioTests(SimpleTestCase):
    def test_nxdomain_es_falso_y_un_fallo_de_red_no_bloquea(self):
        import dns.exception
        import dns.resolver

        from .correo import _dominio_existe
        with mock.patch("dns.resolver.resolve", side_effect=dns.resolver.NXDOMAIN):
            self.assertFalse(_dominio_existe("noexiste.example"))
        with mock.patch("dns.resolver.resolve", side_effect=dns.exception.Timeout):
            self.assertTrue(_dominio_existe("lento.example"))
        with mock.patch("dns.resolver.resolve", return_value=[object()]):
            self.assertTrue(_dominio_existe("existe.example"))

    def test_sin_registro_mx_se_acepta_si_tiene_registro_a(self):
        import dns.resolver

        from .correo import _dominio_existe

        def consulta(dominio, tipo, lifetime=None):
            if tipo == "MX":
                raise dns.resolver.NoAnswer
            return [object()]
        with mock.patch("dns.resolver.resolve", side_effect=consulta):
            self.assertTrue(_dominio_existe("soloa.example"))
        with mock.patch("dns.resolver.resolve", side_effect=dns.resolver.NoAnswer):
            self.assertFalse(_dominio_existe("vacio.example"))


class DistanciaTests(SimpleTestCase):
    def test_distancia_con_transposicion(self):
        from .correo import _distancia
        self.assertEqual(_distancia("gmial", "gmail"), 1)
        self.assertEqual(_distancia("gmail", "gmail"), 0)
        self.assertEqual(_distancia("gmaiil", "gmail"), 1)
        self.assertEqual(_distancia("usat", "usil"), 2)


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
