"""Pruebas de la vista de propuesta (HU-06): disponibilidad del ejecutivo, generación y permisos."""
from datetime import date, datetime
from unittest import mock
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .models import AssistantLink, Availability, MeetingRequest

PW = "Secreto-12345"
LIMA = ZoneInfo("America/Lima")
ANTES = datetime(2026, 10, 26, 6, 0, tzinfo=LIMA)


def mk(email, name, role):
    return User.objects.create_user(username=email, email=email, password=PW, full_name=name, role=role)


class ProposalViewBase(TestCase):
    def setUp(self):
        self.ejec = mk("carla@x.com", "Carla Ejecutiva", "ejecutivo")
        self.asis = mk("ana@x.com", "Ana Asistente", "asistente")
        self.otra = mk("otra@x.com", "Otra Asistente", "asistente")
        AssistantLink.objects.create(assistant=self.asis, executive=self.ejec)
        self.req = MeetingRequest.objects.create(
            executive=self.ejec, created_by=self.asis, title="Revisión trimestral", counterpart_name="Pedro Gómez",
            duration_min=60, week_start=date(2026, 10, 26),
        )
        patcher = mock.patch("django.utils.timezone.now", return_value=ANTES)
        patcher.start()
        self.addCleanup(patcher.stop)

    def login(self, user):
        self.client.logout()
        self.assertTrue(self.client.login(username=user.username, password=PW))

    def av(self, party, blocks):
        return Availability.objects.update_or_create(request=self.req, party=party, defaults={"blocks": blocks})[0]

    def detail(self):
        return self.client.get(reverse("request_detail", args=[self.req.pk]))

    def generate(self, **kw):
        return self.client.post(reverse("generate_proposal", args=[self.req.pk]), **kw)


class ExecutiveAvailabilityTests(ProposalViewBase):
    def test_la_asistente_guarda_la_disponibilidad_del_ejecutivo(self):
        self.login(self.asis)
        r = self.client.post(reverse("save_executive_availability", args=[self.req.pk]), {"b-0-9": "1", "b-1-10": "2"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Availability.objects.get(request=self.req, party="ejecutivo").blocks, {"0-9": 1, "1-10": 2})

    def test_sin_horarios_marcados_no_guarda(self):
        self.login(self.asis)
        r = self.client.post(reverse("save_executive_availability", args=[self.req.pk]), {"b-0-9": "0"}, follow=True)
        self.assertContains(r, "Marca al menos un horario")
        self.assertFalse(Availability.objects.exists())

    def test_una_asistente_sin_vinculo_no_puede_guardar(self):
        self.login(self.otra)
        r = self.client.post(reverse("save_executive_availability", args=[self.req.pk]), {"b-0-9": "1"})
        self.assertEqual(r.status_code, 404)
        self.assertFalse(Availability.objects.exists())

    def test_el_detalle_muestra_lo_ya_guardado(self):
        self.av("ejecutivo", {"3-11": 2})
        self.login(self.asis)
        self.assertContains(self.detail(), 'name="b-3-11" value="2"')

    def test_el_anonimo_no_puede_guardar_ni_generar(self):
        self.assertEqual(self.client.post(reverse("save_executive_availability", args=[self.req.pk])).status_code, 302)
        self.assertEqual(self.generate().status_code, 302)


class GenerateProposalTests(ProposalViewBase):
    def both(self, ej, cp):
        self.av("ejecutivo", ej)
        self.av("contraparte", cp)

    def test_sin_las_dos_disponibilidades_no_se_genera(self):
        self.av("ejecutivo", {"0-9": 1})
        self.login(self.asis)
        r = self.generate(follow=True)
        self.assertContains(r, "aún no está la de la contraparte")
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "pendiente")

    def test_el_boton_se_habilita_solo_con_ambas_disponibilidades(self):
        self.login(self.asis)
        self.assertNotContains(self.detail(), "Generar propuesta de tres horarios")
        self.assertContains(self.detail(), "falta la del ejecutivo y falta la de la contraparte")
        self.both({"0-9": 1}, {"0-9": 1})
        self.assertContains(self.detail(), "Generar propuesta de tres horarios")

    def test_con_coincidencia_muestra_tres_opciones_con_motivo_y_pasa_a_propuesta(self):
        blocks = {f"{d}-10": 1 for d in range(4)}
        self.both(blocks, dict(blocks, **{"2-10": 2}))
        self.login(self.asis)
        r = self.generate(follow=True)
        self.assertContains(r, "Propuesta generada.")
        self.assertContains(r, "Opción 1")
        self.assertContains(r, "Opción 3")
        self.assertNotContains(r, "Opción 4")
        self.assertContains(r, "Pedro Gómez lo marcó como preferido y Carla Ejecutiva también puede.")
        self.assertContains(r, "miércoles, 28 de octubre")
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "propuesta")

    def test_la_primera_opcion_es_la_mejor(self):
        self.both({"0-9": 1, "2-9": 2}, {"0-9": 1, "2-9": 2})
        self.login(self.asis)
        html = self.generate(follow=True).content.decode()
        self.assertLess(html.index("miércoles, 28 de octubre"), html.index("lunes, 26 de octubre"))

    def test_sin_coincidencia_lo_indica_sugiere_ampliar_y_no_cambia_el_estado(self):
        self.both({"0-9": 1}, {"1-9": 1})
        self.login(self.asis)
        r = self.generate(follow=True)
        self.assertContains(r, "No hay un horario en que coincidan las dos partes")
        self.assertContains(r, "Amplía el rango")
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "pendiente")

    def test_si_al_regenerar_ya_no_hay_coincidencia_vuelve_a_pendiente(self):
        self.both({"0-9": 1}, {"0-9": 1})
        self.login(self.asis)
        self.generate()
        self.av("contraparte", {"4-15": 1})
        r = self.generate(follow=True)
        self.assertContains(r, "No hay un horario")
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "pendiente")

    def test_en_una_solicitud_propuesta_el_detalle_recalcula_con_lo_vigente(self):
        self.both({"0-9": 1}, {"0-9": 1})
        self.login(self.asis)
        self.generate()
        self.assertContains(self.detail(), "lunes, 26 de octubre")
        self.av("contraparte", {"0-9": 1, "1-14": 1})
        self.av("ejecutivo", {"0-9": 1, "1-14": 1})
        self.assertContains(self.detail(), "martes, 27 de octubre")

    def test_no_se_proponen_horarios_pasados(self):
        self.both({"0-9": 1}, {"0-9": 1})
        self.login(self.asis)
        with mock.patch("django.utils.timezone.now", return_value=datetime(2026, 10, 26, 12, 0, tzinfo=LIMA)):
            r = self.generate(follow=True)
        self.assertContains(r, "No hay un horario")

    def test_la_duracion_de_la_solicitud_se_respeta(self):
        self.req.duration_min = 90
        self.req.save()
        self.both({"0-9": 1, "0-10": 1, "1-9": 1}, {"0-9": 1, "0-10": 1, "1-9": 1})
        self.login(self.asis)
        r = self.generate(follow=True)
        self.assertContains(r, "09:00 - 10:30")
        self.assertNotContains(r, "martes, 27 de octubre")

    def test_una_asistente_sin_vinculo_no_puede_generar(self):
        self.both({"0-9": 1}, {"0-9": 1})
        self.login(self.otra)
        self.assertEqual(self.generate().status_code, 404)

    def test_generar_exige_post(self):
        self.login(self.asis)
        self.assertEqual(self.client.get(reverse("generate_proposal", args=[self.req.pk])).status_code, 405)

    def test_una_solicitud_cancelada_no_genera(self):
        self.both({"0-9": 1}, {"0-9": 1})
        self.req.status = "cancelada"
        self.req.save()
        self.login(self.asis)
        r = self.generate(follow=True)
        self.assertContains(r, "ya no recibe propuestas")

    def test_el_ejecutivo_dueno_ve_la_propuesta(self):
        self.both({"0-9": 1}, {"0-9": 1})
        self.login(self.asis)
        self.generate()
        self.login(self.ejec)
        self.assertContains(self.detail(), "Opción 1")
