"""Pruebas del onboarding de tres pasos segun el rol (TR-43)."""
from datetime import date, datetime
from unittest import mock
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.urls import reverse

from meetings.models import AssistantLink, Availability, MeetingRequest, SchedulingRule

from .models import Profile, User

PW = "Secreto-12345"
LIMA = ZoneInfo("America/Lima")


def mk(email, name, role):
    return User.objects.create_user(username=email, email=email, password=PW, full_name=name, role=role)


def paso(n):
    return reverse("onboarding_step", args=[n])


class OnboardingBase(TestCase):
    def setUp(self):
        self.ejec = mk("carla@x.com", "Carla Ejecutiva", "ejecutivo")
        self.ejec2 = mk("luis@x.com", "Luis Ejecutivo", "ejecutivo")
        self.asis = mk("ana@x.com", "Ana Asistente", "asistente")

    def login(self, user):
        self.client.logout()
        self.assertTrue(self.client.login(username=user.username, password=PW))

    def profile(self, user):
        return Profile.objects.get(user=user)

    def rules(self, executive):
        return set(SchedulingRule.objects.filter(executive=executive).values_list("weekday", "start_hour", "end_hour"))


class RegistroLlevaAlOnboardingTests(TestCase):
    def registrar(self, role):
        return self.client.post(reverse("signup"), {"full_name": "Nueva Persona", "email": f"{role}@x.com", "role": role,
                                                    "password1": PW, "password2": PW})

    def test_tras_registrarse_ve_el_paso_1_con_progreso_y_omitir(self):
        for role in ("asistente", "ejecutivo"):
            with self.subTest(role=role):
                self.client.logout()
                r = self.registrar(role)
                self.assertRedirects(r, reverse("onboarding"))
                r = self.client.get(reverse("onboarding"))
                self.assertContains(r, "Paso 1 de 3")
                self.assertContains(r, 'aria-valuenow="1"')
                self.assertContains(r, "Omitir por ahora")
                self.assertContains(r, f"Te registraste como <strong>{role.capitalize()}</strong>")

    def test_el_panel_de_apoyo_muestra_la_tarjeta_de_ejemplo(self):
        self.registrar("ejecutivo")
        r = self.client.get(reverse("onboarding"))
        self.assertContains(r, "Revisión trimestral de ventas")
        self.assertContains(r, "Opción 3")
        self.assertContains(r, "Ejemplo con datos ficticios.")


class PermisosTests(OnboardingBase):
    def test_sin_sesion_lleva_al_ingreso(self):
        for url in (reverse("onboarding"), paso(1), paso(2), paso(3)):
            with self.subTest(url=url):
                r = self.client.get(url)
                self.assertEqual(r.status_code, 302)
                self.assertTrue(r["Location"].startswith(reverse("login")))
        r = self.client.post(reverse("skip_onboarding"))
        self.assertTrue(r["Location"].startswith(reverse("login")))

    def test_un_paso_que_no_existe_da_404(self):
        self.login(self.ejec)
        self.assertEqual(self.client.get(paso(4)).status_code, 404)

    def test_omitir_solo_acepta_post(self):
        self.login(self.ejec)
        self.assertEqual(self.client.get(reverse("skip_onboarding")).status_code, 405)

    def test_los_formularios_llevan_csrf(self):
        self.login(self.ejec)
        for n in (1, 2, 3):
            with self.subTest(paso=n):
                html = self.client.get(paso(n)).content.decode()
                formularios = html.split('<main')[1].split("</main>")[0].split("<form")[1:]
                self.assertEqual(len(formularios), 2)  # el del paso y el de omitir
                self.assertTrue(all("csrfmiddlewaretoken" in f for f in formularios))

    def test_la_asistente_no_puede_crear_reglas_para_un_ejecutivo_no_vinculado(self):
        AssistantLink.objects.create(assistant=self.asis, executive=self.ejec)
        self.login(self.asis)
        r = self.client.post(paso(3), {"executive": self.ejec2.pk, "protect": ["antes_10"]})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.rules(self.ejec2), set())

    def test_el_ejecutivo_solo_crea_reglas_para_si_mismo(self):
        self.login(self.ejec)
        r = self.client.post(paso(3), {"executive": self.ejec2.pk, "protect": ["antes_10"]})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.rules(self.ejec2), set())

    def test_los_usuarios_que_ya_existian_no_son_obligados_a_verlo(self):
        self.login(self.ejec)
        self.assertEqual(self.client.get(reverse("panel")).status_code, 200)


class Paso1AreaTests(OnboardingBase):
    def test_guarda_el_area_y_pasa_al_paso_2(self):
        self.login(self.ejec)
        r = self.client.post(paso(1), {"area": "finanzas"})
        self.assertRedirects(r, paso(2), fetch_redirect_response=False)
        self.assertEqual(self.profile(self.ejec).area, "finanzas")

    def test_exige_elegir_un_area(self):
        self.login(self.ejec)
        r = self.client.post(paso(1), {})
        self.assertContains(r, "Elige el área en la que trabajas.", status_code=400)

    def test_muestra_el_rol_del_registro_sin_volver_a_preguntarlo(self):
        self.login(self.asis)
        r = self.client.get(paso(1))
        self.assertContains(r, "Te registraste como <strong>Asistente</strong>")
        self.assertNotContains(r, 'name="role"')

    def test_el_paso_1_no_cambia_el_rol_aunque_se_envie(self):
        self.login(self.asis)
        r = self.client.post(paso(1), {"role": "ejecutivo", "area": "direccion"})
        self.assertRedirects(r, paso(2), fetch_redirect_response=False)
        self.asis.refresh_from_db()
        self.assertTrue(self.asis.is_assistant)
        self.assertIsNone(self.asis.link_code)
        self.assertContains(self.client.get(paso(2)), "Vincúlate con tu ejecutivo")


class Paso2EjecutivoTests(OnboardingBase):
    def test_propone_de_9_a_18_por_defecto(self):
        self.login(self.ejec)
        r = self.client.get(paso(2))
        self.assertContains(r, '<option value="9" selected>09:00</option>', html=True)
        self.assertContains(r, '<option value="18" selected>18:00</option>', html=True)
        self.assertContains(r, "Las horas se muestran en hora de Lima.")
        self.assertNotContains(r, "Zona horaria")
        self.assertContains(r, "Paso 2 de 3")

    def test_guarda_la_jornada(self):
        self.login(self.ejec)
        r = self.client.post(paso(2), {"work_start": 8, "work_end": 17})
        self.assertRedirects(r, paso(3), fetch_redirect_response=False)
        p = self.profile(self.ejec)
        self.assertEqual((p.work_start, p.work_end), (8, 17))

    def test_rechaza_una_jornada_al_reves(self):
        self.login(self.ejec)
        r = self.client.post(paso(2), {"work_start": 18, "work_end": 9})
        self.assertContains(r, "La jornada debe terminar después de empezar.", status_code=400)

    def test_rechaza_horas_fuera_de_rango(self):
        self.login(self.ejec)
        r = self.client.post(paso(2), {"work_start": 9, "work_end": 30})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.profile(self.ejec).work_end, 18)


class Paso2AsistenteTests(OnboardingBase):
    def test_pide_el_codigo_del_ejecutivo(self):
        self.login(self.asis)
        r = self.client.get(paso(2))
        self.assertContains(r, "Vincúlate con tu ejecutivo")
        self.assertContains(r, 'for="codigo-vinculo"')
        self.assertContains(r, "Continuar sin código")

    def test_con_un_codigo_valido_queda_vinculada(self):
        self.login(self.asis)
        r = self.client.post(paso(2), {"code": self.ejec.link_code.lower()})
        self.assertRedirects(r, paso(3), fetch_redirect_response=False)
        self.assertTrue(AssistantLink.objects.filter(assistant=self.asis, executive=self.ejec).exists())

    def test_con_un_codigo_inexistente_muestra_el_error(self):
        self.login(self.asis)
        r = self.client.post(paso(2), {"code": "ZZZZZZ"})
        self.assertContains(r, "Ese código no existe", status_code=400)
        self.assertFalse(AssistantLink.objects.filter(assistant=self.asis).exists())


class Paso3HorariosProtegidosTests(OnboardingBase):
    def test_el_ejecutivo_crea_reglas_reales_y_termina(self):
        self.login(self.ejec)
        r = self.client.post(paso(3), {"executive": self.ejec.pk, "protect": ["antes_10", "refrigerio", "viernes_tarde"]})
        self.assertRedirects(r, reverse("panel") + "#vinculacion", fetch_redirect_response=False)
        self.assertEqual(self.rules(self.ejec), {(None, 0, 10), (None, 13, 14), (4, 14, 24)})
        self.assertTrue(all(rule.created_by == self.ejec and rule.active for rule in SchedulingRule.objects.all()))
        self.assertIsNotNone(self.profile(self.ejec).onboarding_completed_at)

    def test_al_terminar_el_ejecutivo_ve_su_codigo(self):
        self.login(self.ejec)
        r = self.client.post(paso(3), {"executive": self.ejec.pk, "protect": ["antes_10"]}, follow=True)
        self.assertContains(r, "Se creó 1 regla de horarios protegidos.")
        self.assertContains(r, f"Tu código de vinculación es {self.ejec.link_code}")

    def test_fuera_de_la_jornada_usa_la_jornada_registrada(self):
        self.login(self.ejec)
        self.client.post(paso(2), {"work_start": 8, "work_end": 17})
        self.assertContains(self.client.get(paso(3)), "Fuera de mi jornada (08:00 a 17:00)")
        self.client.post(paso(3), {"executive": self.ejec.pk, "protect": ["fuera_jornada"]})
        self.assertEqual(self.rules(self.ejec), {(None, 0, 8), (None, 17, 24)})

    def test_no_duplica_reglas_que_ya_existen(self):
        SchedulingRule.objects.create(executive=self.ejec, created_by=self.ejec, weekday=None, start_hour=0, end_hour=10, active=False)
        self.login(self.ejec)
        r = self.client.post(paso(3), {"executive": self.ejec.pk, "protect": ["antes_10", "refrigerio"]}, follow=True)
        self.assertEqual(SchedulingRule.objects.filter(executive=self.ejec).count(), 2)
        self.assertFalse(SchedulingRule.objects.get(executive=self.ejec, start_hour=0).active)
        self.assertContains(r, "Se creó 1 regla")

    def test_terminar_sin_marcar_nada_no_crea_reglas(self):
        self.login(self.ejec)
        r = self.client.post(paso(3), {"executive": self.ejec.pk}, follow=True)
        self.assertContains(r, "Se crearon 0 reglas")
        self.assertEqual(self.rules(self.ejec), set())

    def test_la_asistente_vinculada_crea_reglas_para_su_ejecutivo(self):
        AssistantLink.objects.create(assistant=self.asis, executive=self.ejec)
        self.login(self.asis)
        r = self.client.get(paso(3))
        self.assertContains(r, "Fuera de la jornada del ejecutivo")
        r = self.client.post(paso(3), {"executive": self.ejec.pk, "protect": ["refrigerio", "fuera_jornada"]})
        self.assertRedirects(r, reverse("panel"), fetch_redirect_response=False)
        self.assertEqual(self.rules(self.ejec), {(None, 13, 14), (None, 0, 9), (None, 18, 24)})
        self.assertTrue(all(rule.created_by == self.asis for rule in SchedulingRule.objects.all()))

    def test_la_asistente_sin_vinculo_va_a_la_pantalla_de_reglas(self):
        self.login(self.asis)
        r = self.client.get(paso(3), follow=True)
        self.assertRedirects(r, reverse("rules"))
        self.assertContains(r, "primero vincúlate con un ejecutivo")
        self.assertIsNotNone(self.profile(self.asis).onboarding_completed_at)


class NoSeRepiteTests(OnboardingBase):
    def test_quien_lo_completo_no_vuelve_a_verlo(self):
        self.login(self.ejec)
        self.client.post(paso(3), {"executive": self.ejec.pk, "protect": ["antes_10"]})
        for url in (reverse("onboarding"), paso(1), paso(2), paso(3)):
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), reverse("panel"))
        self.client.post(paso(3), {"executive": self.ejec.pk, "protect": ["refrigerio"]})
        self.assertEqual(self.rules(self.ejec), {(None, 0, 10)})

    def test_quien_lo_omitio_no_vuelve_a_verlo(self):
        self.login(self.asis)
        r = self.client.post(reverse("skip_onboarding"), follow=True)
        self.assertRedirects(r, reverse("panel"))
        self.assertContains(r, "Puedes configurar tus horarios protegidos cuando quieras")
        self.assertIsNotNone(self.profile(self.asis).onboarding_skipped_at)
        self.assertRedirects(self.client.get(reverse("onboarding")), reverse("panel"))

    def test_omitir_en_medio_conserva_lo_ya_respondido(self):
        self.login(self.ejec)
        self.client.post(paso(1), {"area": "legal"})
        self.client.post(reverse("skip_onboarding"))
        p = self.profile(self.ejec)
        self.assertEqual(p.area, "legal")
        self.assertIsNone(p.onboarding_completed_at)
        self.assertTrue(p.onboarding_done)


class FlujoCompletoTests(OnboardingBase):
    def test_flujo_completo_del_ejecutivo(self):
        self.login(self.ejec)
        self.client.post(paso(1), {"area": "direccion"})
        self.client.post(paso(2), {"work_start": 9, "work_end": 18})
        self.client.post(paso(3), {"executive": self.ejec.pk, "protect": ["refrigerio", "fuera_jornada"]})
        p = self.profile(self.ejec)
        self.assertEqual((p.area, p.work_start, p.work_end), ("direccion", 9, 18))
        self.assertTrue(p.onboarding_done)
        self.assertEqual(self.rules(self.ejec), {(None, 13, 14), (None, 0, 9), (None, 18, 24)})

    def test_flujo_completo_de_la_asistente(self):
        self.login(self.asis)
        self.client.post(paso(1), {"area": "comercial"})
        self.client.post(paso(2), {"code": self.ejec.link_code})
        self.client.post(paso(3), {"executive": self.ejec.pk, "protect": ["antes_10"]})
        self.assertEqual(self.profile(self.asis).area, "comercial")
        self.assertTrue(AssistantLink.objects.filter(assistant=self.asis, executive=self.ejec).exists())
        self.assertEqual(self.rules(self.ejec), {(None, 0, 10)})
        self.assertTrue(self.profile(self.asis).onboarding_done)


class LasReglasAfectanLaPropuestaTests(OnboardingBase):
    """Las reglas creadas en el paso 3 se respetan al generar la propuesta de horarios."""

    def setUp(self):
        super().setUp()
        AssistantLink.objects.create(assistant=self.asis, executive=self.ejec)
        self.req = MeetingRequest.objects.create(
            executive=self.ejec, created_by=self.asis, title="Revisión", counterpart_name="Pedro Gómez",
            duration_min=60, week_start=date(2026, 10, 26))
        blocks = {"0-9": 1, "0-11": 1, "0-13": 1}
        for party in ("ejecutivo", "contraparte"):
            Availability.objects.create(request=self.req, party=party, blocks=blocks)
        patcher = mock.patch("django.utils.timezone.now", return_value=datetime(2026, 10, 26, 6, 0, tzinfo=LIMA))
        patcher.start()
        self.addCleanup(patcher.stop)

    def generate(self):
        self.login(self.asis)
        return self.client.post(reverse("generate_proposal", args=[self.req.pk]), follow=True)

    def test_sin_onboarding_se_proponen_las_9_y_las_13(self):
        r = self.generate()
        self.assertContains(r, "09:00 - 10:00")
        self.assertContains(r, "13:00 - 14:00")

    def test_con_las_reglas_del_onboarding_no_se_proponen(self):
        self.login(self.ejec)
        self.client.post(paso(3), {"executive": self.ejec.pk, "protect": ["antes_10", "refrigerio"]})
        r = self.generate()
        self.assertNotContains(r, "09:00 - 10:00")
        self.assertNotContains(r, "13:00 - 14:00")
        self.assertContains(r, "11:00 - 12:00")
