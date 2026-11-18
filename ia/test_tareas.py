"""Pruebas del tablero de tareas y la exportacion CSV (HU-19): permisos, filtros, estado y contenido del CSV."""
import csv
import io
from datetime import date, datetime, timezone as tz
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from meetings.models import AssistantLink, MeetingRequest

from .models import AcuerdosReunion, TareaReunion
from .tareas import COLUMNAS_CSV, _celda

User = get_user_model()


class TareasBase(TestCase):
    def setUp(self):
        def crear(correo, nombre, rol):
            return User.objects.create_user(
                username=correo, email=correo, password="clave-larga-123", full_name=nombre, role=rol
            )

        self.ejecutivo = crear("ejec@e.pe", "Rocío Ejecutiva", "ejecutivo")
        self.otro_ejecutivo = crear("otro@e.pe", "Otro Ejecutivo", "ejecutivo")
        self.asistente = crear("asis@e.pe", "Ana Asistente", "asistente")
        self.sin_vinculo = crear("sola@e.pe", "Sola Asistente", "asistente")
        AssistantLink.objects.create(assistant=self.asistente, executive=self.ejecutivo)
        self.contrato = self.reunion(self.ejecutivo, "Revisar el contrato", "Proveedor de Alicorp")
        self.presupuesto = self.reunion(self.ejecutivo, "Presupuesto 2027", "Finanzas")
        self.ajena = self.reunion(self.otro_ejecutivo, "Reunión reservada", "Competidor")
        self.t1 = self.tarea(self.contrato, "Enviar la versión final", "Luis", date(2026, 11, 20))
        self.t2 = self.tarea(self.contrato, "Confirmar el presupuesto", "Ana", None)
        self.t3 = self.tarea(self.presupuesto, "Cerrar la proyección", "Mónica", date(2026, 12, 1), hecha=True)
        self.secreta = self.tarea(self.ajena, "Tarea secreta ajena", "Nadie", None)
        self.url = reverse("ia_tareas")
        self.csv = reverse("ia_tareas_csv")

    def reunion(self, ejecutivo, titulo, contraparte):
        return MeetingRequest.objects.create(
            executive=ejecutivo,
            created_by=self.asistente,
            title=titulo,
            counterpart_name=contraparte,
            status=MeetingRequest.Status.APROBADA,
            approved_start=datetime(2026, 11, 20, 15, 0, tzinfo=tz.utc),
            approved_end=datetime(2026, 11, 20, 16, 0, tzinfo=tz.utc),
        )

    def tarea(self, reunion, descripcion, responsable, fecha, hecha=False):
        acuerdos, _ = AcuerdosReunion.objects.get_or_create(
            request=reunion, defaults=dict(notas="n", resumen="r", created_by=self.asistente)
        )
        return TareaReunion.objects.create(
            acuerdos=acuerdos, descripcion=descripcion, responsable=responsable, fecha_limite=fecha, hecha=hecha
        )

    def entrar(self, usuario):
        self.client.force_login(usuario)

    def filas_csv(self, respuesta):
        texto = respuesta.content.decode("utf-8-sig")
        return list(csv.reader(io.StringIO(texto)))


class TableroTests(TareasBase):
    def test_exige_sesion_y_solo_acepta_lectura(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.assertEqual(self.client.get(self.csv).status_code, 302)
        self.assertEqual(self.client.post(reverse("ia_tarea_estado", args=[self.t1.pk])).status_code, 302)
        self.entrar(self.asistente)
        self.assertEqual(self.client.post(self.url).status_code, 405)
        self.assertEqual(self.client.post(self.csv).status_code, 405)
        self.assertEqual(self.client.get(reverse("ia_tarea_estado", args=[self.t1.pk])).status_code, 405)

    def test_la_asistente_ve_las_tareas_de_sus_ejecutivos_y_no_las_ajenas(self):
        self.entrar(self.asistente)
        respuesta = self.client.get(self.url)
        esperados = ("Enviar la versión final", "Confirmar el presupuesto", "Cerrar la proyección", "Luis", "20/11")
        for texto in esperados:
            self.assertContains(respuesta, texto)
        self.assertNotContains(respuesta, "Tarea secreta ajena")
        self.assertContains(respuesta, "2 pendientes de 3")

    def test_el_ejecutivo_ve_solo_las_suyas(self):
        self.entrar(self.ejecutivo)
        self.assertContains(self.client.get(self.url), "Enviar la versión final")
        self.assertNotContains(self.client.get(self.url), "Tarea secreta ajena")
        self.entrar(self.otro_ejecutivo)
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, "Tarea secreta ajena")
        self.assertNotContains(respuesta, "Enviar la versión final")

    def test_quien_no_ve_ninguna_reunion_ve_el_estado_vacio(self):
        self.entrar(self.sin_vinculo)
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, "Todavía no hay tareas")
        self.assertNotContains(respuesta, "Enviar la versión final")

    def test_pendientes_primero_y_por_fecha_con_las_sin_fecha_al_final(self):
        self.entrar(self.asistente)
        orden = [t.descripcion for t in self.client.get(self.url).context["tareas"]]
        self.assertEqual(orden, ["Enviar la versión final", "Confirmar el presupuesto", "Cerrar la proyección"])

    def test_filtra_por_estado(self):
        self.entrar(self.asistente)
        pendientes = self.client.get(self.url, {"estado": "pendiente"})
        self.assertEqual({t.pk for t in pendientes.context["tareas"]}, {self.t1.pk, self.t2.pk})
        hechas = self.client.get(self.url, {"estado": "hecha"})
        self.assertEqual([t.pk for t in hechas.context["tareas"]], [self.t3.pk])

    def test_filtra_por_reunion(self):
        self.entrar(self.asistente)
        respuesta = self.client.get(self.url, {"reunion": self.presupuesto.pk})
        self.assertEqual([t.pk for t in respuesta.context["tareas"]], [self.t3.pk])

    def test_los_filtros_se_combinan(self):
        self.entrar(self.asistente)
        respuesta = self.client.get(self.url, {"estado": "pendiente", "reunion": self.presupuesto.pk})
        self.assertEqual(respuesta.context["tareas"], [])
        self.assertContains(respuesta, "Ninguna tarea coincide con el filtro.")

    def test_filtrar_por_la_reunion_de_otro_no_revela_sus_tareas(self):
        self.entrar(self.asistente)
        respuesta = self.client.get(self.url, {"reunion": self.ajena.pk})
        self.assertEqual(respuesta.context["tareas"], [])
        self.assertNotContains(respuesta, "Tarea secreta ajena")
        self.assertNotContains(respuesta, "Reunión reservada")  # tampoco aparece en el selector

    def test_valores_de_filtro_raros_se_ignoran(self):
        self.entrar(self.asistente)
        respuesta = self.client.get(self.url, {"estado": "<script>", "reunion": "abc"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context["tareas"]), 3)
        self.assertEqual(respuesta.context["filtros"], {"estado": "", "reunion": ""})

    def test_marca_las_vencidas_solo_si_siguen_pendientes(self):
        self.entrar(self.asistente)
        with mock.patch("ia.tareas.timezone.localdate", return_value=date(2026, 12, 15)):
            tareas = {t.pk: t for t in self.client.get(self.url).context["tareas"]}
        self.assertTrue(tareas[self.t1.pk].vencida)
        self.assertFalse(tareas[self.t2.pk].vencida)  # sin fecha
        self.assertFalse(tareas[self.t3.pk].vencida)  # vencida pero hecha

    def test_el_enlace_de_exportar_conserva_los_filtros(self):
        self.entrar(self.asistente)
        respuesta = self.client.get(self.url, {"estado": "pendiente"})
        self.assertContains(respuesta, f'href="{self.csv}?estado=pendiente"')

    def test_aparece_en_el_menu_lateral(self):
        self.entrar(self.asistente)
        self.assertContains(self.client.get(reverse("panel")), f'href="{self.url}"')


class CambiarEstadoTests(TareasBase):
    def estado(self, tarea, **extra):
        return self.client.post(reverse("ia_tarea_estado", args=[tarea.pk]), extra)

    def test_marca_como_hecha_y_reabre(self):
        self.entrar(self.asistente)
        respuesta = self.estado(self.t1)
        self.assertRedirects(respuesta, self.url, fetch_redirect_response=False)
        self.t1.refresh_from_db()
        self.assertTrue(self.t1.hecha)
        self.assertEqual([str(m) for m in get_messages(respuesta.wsgi_request)], ["Tarea marcada como hecha."])
        respuesta = self.estado(self.t1)
        self.t1.refresh_from_db()
        self.assertFalse(self.t1.hecha)
        self.assertEqual([str(m) for m in get_messages(respuesta.wsgi_request)][-1], "Tarea reabierta.")

    def test_el_ejecutivo_tambien_puede_cambiar_el_estado(self):
        self.entrar(self.ejecutivo)
        self.estado(self.t2)
        self.t2.refresh_from_db()
        self.assertTrue(self.t2.hecha)

    def test_vuelve_al_tablero_con_el_mismo_filtro(self):
        self.entrar(self.asistente)
        respuesta = self.estado(self.t1, estado="pendiente", reunion=str(self.contrato.pk))
        self.assertEqual(respuesta["Location"], f"{self.url}?estado=pendiente&reunion={self.contrato.pk}")

    def test_no_redirige_a_donde_diga_el_formulario(self):
        self.entrar(self.asistente)
        respuesta = self.estado(
            self.t1, estado="https://malo.example", reunion="//malo.example", next="https://malo.example"
        )
        self.assertEqual(respuesta["Location"], self.url)

    def test_una_tarea_ajena_da_404_y_no_cambia(self):
        casos = [(self.sin_vinculo, self.t1), (self.asistente, self.secreta), (self.ejecutivo, self.secreta)]
        for usuario, tarea in casos:
            self.entrar(usuario)
            self.assertEqual(self.estado(tarea).status_code, 404)
        self.secreta.refresh_from_db()
        self.t1.refresh_from_db()
        self.assertFalse(self.secreta.hecha)
        self.assertFalse(self.t1.hecha)

    def test_una_tarea_que_no_existe_da_404(self):
        self.entrar(self.asistente)
        self.assertEqual(self.client.post(reverse("ia_tarea_estado", args=[99999])).status_code, 404)


class ExportarCsvTests(TareasBase):
    def test_descarga_en_utf8_con_las_columnas_indicadas(self):
        self.entrar(self.asistente)
        respuesta = self.client.get(self.csv)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment", respuesta["Content-Disposition"])
        self.assertIn("tareas_quedamos.csv", respuesta["Content-Disposition"])
        self.assertTrue(respuesta.content.startswith(b"\xef\xbb\xbf"))  # BOM: Excel respeta tildes y eñes
        filas = self.filas_csv(respuesta)
        self.assertEqual(tuple(filas[0]), COLUMNAS_CSV)
        self.assertEqual(filas[0], ["Resumen", "Descripción", "Tipo", "Fecha límite", "Etiquetas"])

    def test_el_contenido_de_cada_fila(self):
        self.entrar(self.asistente)
        filas = self.filas_csv(self.client.get(self.csv))
        self.assertEqual(len(filas), 4)  # encabezado + 3 tareas, sin la ajena
        primera = filas[1]
        self.assertEqual(primera[0], "Enviar la versión final")
        self.assertIn("Revisar el contrato", primera[1])
        self.assertIn("Proveedor de Alicorp", primera[1])
        self.assertIn("Responsable: Luis", primera[1])
        self.assertEqual(primera[2:], ["Tarea", "2026-11-20", "quedamos-ia"])
        self.assertNotIn("Tarea secreta ajena", "".join("".join(f) for f in filas))

    def test_una_tarea_sin_fecha_exporta_la_celda_vacia(self):
        self.entrar(self.asistente)
        filas = {f[0]: f for f in self.filas_csv(self.client.get(self.csv))}
        self.assertEqual(filas["Confirmar el presupuesto"][3], "")

    def test_sin_responsable_la_descripcion_no_lo_menciona(self):
        self.t2.responsable = ""
        self.t2.save()
        self.entrar(self.asistente)
        filas = {f[0]: f for f in self.filas_csv(self.client.get(self.csv))}
        self.assertNotIn("Responsable", filas["Confirmar el presupuesto"][1])

    def test_respeta_los_filtros(self):
        self.entrar(self.asistente)
        filas = self.filas_csv(self.client.get(self.csv, {"estado": "pendiente", "reunion": self.contrato.pk}))
        self.assertEqual([f[0] for f in filas[1:]], ["Enviar la versión final", "Confirmar el presupuesto"])

    def test_los_acentos_y_las_enies_sobreviven(self):
        self.tarea(self.contrato, "Preparar la presentación para el año próximo", "Íñigo Núñez", None)
        self.entrar(self.ejecutivo)
        texto = self.client.get(self.csv).content.decode("utf-8")
        self.assertIn("Preparar la presentación para el año próximo", texto)
        self.assertIn("Responsable: Íñigo Núñez", texto)

    def test_comas_comillas_y_saltos_de_linea_se_escapan(self):
        self.tarea(self.contrato, 'Enviar "borrador", revisado\ny firmado', "Luis, Ana", None)
        self.entrar(self.asistente)
        filas = self.filas_csv(self.client.get(self.csv))
        self.assertIn('Enviar "borrador", revisado\ny firmado', [f[0] for f in filas])

    def test_neutraliza_las_celdas_que_parecen_formulas(self):
        self.tarea(self.contrato, "=HYPERLINK(\"http://malo.example\")", "+cmd", None)
        self.tarea(self.contrato, "@SUM(1+1)", "x", None)
        self.entrar(self.asistente)
        resumenes = [f[0] for f in self.filas_csv(self.client.get(self.csv))]
        self.assertIn("'=HYPERLINK(\"http://malo.example\")", resumenes)
        self.assertIn("'@SUM(1+1)", resumenes)
        self.assertFalse([r for r in resumenes if r[:1] in "=+-@"])

    def test_la_funcion_de_celda(self):
        self.assertEqual(_celda(None), "")
        self.assertEqual(_celda("normal"), "normal")
        self.assertEqual(_celda("-1"), "'-1")
        self.assertEqual(_celda("\tx"), "'\tx")

    def test_sin_tareas_solo_trae_el_encabezado(self):
        self.entrar(self.sin_vinculo)
        self.assertEqual(len(self.filas_csv(self.client.get(self.csv))), 1)

    def test_un_usuario_ajeno_no_recibe_tareas_de_otros_en_el_csv(self):
        self.entrar(self.otro_ejecutivo)
        resumenes = [f[0] for f in self.filas_csv(self.client.get(self.csv))[1:]]
        self.assertEqual(resumenes, ["Tarea secreta ajena"])


class DetalleTests(TareasBase):
    def test_el_detalle_enlaza_al_tablero_filtrado_por_esa_reunion(self):
        self.entrar(self.asistente)
        respuesta = self.client.get(reverse("request_detail", args=[self.contrato.pk]))
        self.assertContains(respuesta, f"{self.url}?reunion={self.contrato.pk}")
