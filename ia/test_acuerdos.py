"""Pruebas de los acuerdos de la reunion (HU-18): generacion, edicion, permisos, salida invalida y cupo.

Gemini siempre simulado: las vistas parchean `pedir_json` y las pruebas de integracion parchean el envio por red.
"""
import json
from datetime import date, datetime, timezone as tz
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from meetings.models import AssistantLink, MeetingRequest

from . import acuerdos
from .gemini import CupoDiarioAgotado, EntradaInvalida, IaNoDisponible
from .models import AcuerdosReunion, TareaReunion, UsoIA

User = get_user_model()
CLAVE = dict(
    GEMINI_API_KEY="clave-de-prueba", GEMINI_MODEL="m1", GEMINI_MODEL_FALLBACK="m2", IA_LLAMADAS_POR_USUARIO_DIA=30
)
NOTAS = (
    "Revisamos el contrato. Luis envía la versión final el viernes. Ana confirma el presupuesto. "
    "Nos vemos de nuevo en dos semanas."
)


def salida(**cambios):
    base = {
        "resumen": "Se revisó el contrato.",
        "tareas": [
            {"descripcion": "Enviar la versión final", "responsable": "Luis", "fecha_limite": "2026-11-20"},
            {"descripcion": "Confirmar el presupuesto", "responsable": "Ana", "fecha_limite": None},
        ],
        "seguimiento": {"asunto": "Seguimiento del contrato", "duracion_min": 45},
    }
    base.update(cambios)
    return base


def respuesta_gemini(objeto):
    texto = objeto if isinstance(objeto, str) else json.dumps(objeto)
    return 200, {"candidates": [{"content": {"parts": [{"text": texto}]}}]}


@override_settings(**CLAVE)
class AcuerdosBase(TestCase):
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
        self.reunion = MeetingRequest.objects.create(
            executive=self.ejecutivo,
            created_by=self.asistente,
            title="Revisar el contrato",
            duration_min=60,
            counterpart_name="Proveedor de Alicorp",
            counterpart_email="prov@alicorp.pe",
            status=MeetingRequest.Status.APROBADA,
            approved_start=datetime(2026, 11, 20, 15, 0, tzinfo=tz.utc),
            approved_end=datetime(2026, 11, 20, 16, 0, tzinfo=tz.utc),
        )
        self.generar = reverse("ia_acuerdos_generar", args=[self.reunion.pk])
        self.confirmar = reverse("ia_acuerdos_confirmar", args=[self.reunion.pk])
        self.seguimiento = reverse("ia_seguimiento", args=[self.reunion.pk])
        self.detalle = reverse("request_detail", args=[self.reunion.pk])

    def entrar(self, usuario):
        self.client.force_login(usuario)

    def pedir_vista_previa(self, notas=NOTAS, datos=None):
        with mock.patch("ia.views.pedir_json", return_value=datos or salida()) as simulado:
            respuesta = self.client.post(self.generar, {"notas": notas})
        return respuesta, simulado

    def confirmar_con(self, **extra):
        """Envia lo que mandaria la vista previa con dos tareas y un seguimiento, mas los cambios indicados."""
        datos = {
            "notas": NOTAS,
            "total": "4",
            "resumen": "Se revisó el contrato.",
            "t0-incluir": "1",
            "t0-descripcion": "Enviar la versión final",
            "t0-responsable": "Luis",
            "t0-fecha_limite": "2026-11-20",
            "t1-incluir": "1",
            "t1-descripcion": "Confirmar el presupuesto",
            "t1-responsable": "Ana",
            "t1-fecha_limite": "",
            "t2-incluir": "1",
            "t2-descripcion": "",
            "t2-responsable": "",
            "t2-fecha_limite": "",
            "t3-incluir": "1",
            "t3-descripcion": "",
            "t3-responsable": "",
            "t3-fecha_limite": "",
            "seguimiento_incluir": "on",
            "seguimiento_asunto": "Seguimiento del contrato",
            "seguimiento_duracion": "45",
        }
        datos.update(extra)
        datos = {k: v for k, v in datos.items() if v is not None}
        return self.client.post(self.confirmar, datos)


class SeccionTests(AcuerdosBase):
    def test_la_asistente_ve_la_seccion_en_una_reunion_aprobada(self):
        self.entrar(self.asistente)
        respuesta = self.client.get(self.detalle)
        self.assertContains(respuesta, "Después de la reunión")
        self.assertContains(respuesta, 'name="notas"')
        self.assertContains(respuesta, "6000")
        self.assertContains(respuesta, "se envía a Gemini")

    def test_solo_las_solicitudes_aprobadas_muestran_la_seccion(self):
        self.entrar(self.asistente)
        for estado in ("pendiente", "propuesta", "cancelada"):
            self.reunion.status = estado
            self.reunion.save()
            self.assertNotContains(self.client.get(self.detalle), "Después de la reunión", msg_prefix=estado)

    @override_settings(GEMINI_API_KEY="")
    def test_sin_clave_no_se_ofrece_generar_y_el_detalle_sigue_igual(self):
        self.entrar(self.asistente)
        respuesta = self.client.get(self.detalle)
        self.assertNotContains(respuesta, "Después de la reunión")
        self.assertContains(respuesta, "Aprobada por el ejecutivo")

    def test_el_ejecutivo_no_ve_el_formulario_de_generacion(self):
        self.entrar(self.ejecutivo)
        self.assertNotContains(self.client.get(self.detalle), "Después de la reunión")

    def test_con_acuerdos_guardados_se_muestran_a_ejecutivo_y_asistente_aun_sin_clave(self):
        self.entrar(self.asistente)
        self.pedir_vista_previa()
        self.confirmar_con()
        for usuario in (self.asistente, self.ejecutivo):
            self.entrar(usuario)
            with override_settings(GEMINI_API_KEY=""):
                respuesta = self.client.get(self.detalle)
            self.assertContains(respuesta, "Después de la reunión")
            self.assertContains(respuesta, "Enviar la versión final")
            self.assertContains(respuesta, "Luis")
            self.assertContains(respuesta, "20/11/2026")
            self.assertContains(respuesta, "Seguimiento del contrato · 45 min")
            self.assertNotContains(respuesta, 'name="notas"')
        self.assertContains(respuesta, "Registrado por Ana Asistente")

    def test_solo_la_asistente_ve_el_boton_de_seguimiento(self):
        self.entrar(self.asistente)
        self.confirmar_con()
        self.assertContains(self.client.get(self.detalle), "Proponer seguimiento")
        self.entrar(self.ejecutivo)
        self.assertNotContains(self.client.get(self.detalle), "Proponer seguimiento")

    def test_sin_tareas_ni_seguimiento_lo_dice(self):
        self.entrar(self.asistente)
        self.confirmar_con(total="1", **{"t0-descripcion": "", "t0-responsable": "", "t0-fecha_limite": ""},
                           seguimiento_incluir=None)
        respuesta = self.client.get(self.detalle)
        self.assertContains(respuesta, "Las notas no dejaron tareas.")
        self.assertNotContains(respuesta, "Seguimiento propuesto")


class GeneracionTests(AcuerdosBase):
    def setUp(self):
        super().setUp()
        self.entrar(self.asistente)

    def test_la_vista_previa_muestra_resumen_tareas_y_seguimiento_sin_guardar_nada(self):
        respuesta, simulado = self.pedir_vista_previa()
        self.assertContains(respuesta, "Se revisó el contrato.")
        self.assertContains(respuesta, 'value="Enviar la versión final"')
        self.assertContains(respuesta, 'value="Luis"')
        self.assertContains(respuesta, 'value="2026-11-20"')
        self.assertContains(respuesta, 'value="Confirmar el presupuesto"')
        self.assertContains(respuesta, 'value="Seguimiento del contrato"')
        self.assertContains(respuesta, '<option value="45" selected>')
        self.assertContains(respuesta, "Confirmar acuerdos")
        self.assertEqual(AcuerdosReunion.objects.count(), 0)
        self.assertEqual(TareaReunion.objects.count(), 0)
        self.assertEqual(simulado.call_args.args[0], self.asistente)
        self.assertEqual(simulado.call_args.args[2], NOTAS)
        self.assertEqual(simulado.call_args.kwargs["max_chars"], 6000)

    def test_hay_filas_vacias_para_agregar_tareas(self):
        respuesta, _ = self.pedir_vista_previa()
        self.assertContains(respuesta, 'name="total" value="4"')  # 2 tareas + 2 filas extra
        self.assertContains(respuesta, 'name="t3-descripcion"')

    def test_las_notas_viajan_en_la_vista_previa_para_guardarlas_al_confirmar(self):
        respuesta, _ = self.pedir_vista_previa()
        self.assertContains(respuesta, 'name="notas"')
        self.assertContains(respuesta, "Revisamos el contrato.")

    def test_sin_seguimiento_la_casilla_queda_sin_marcar(self):
        respuesta, _ = self.pedir_vista_previa(datos=salida(seguimiento=None))
        html = respuesta.content.decode()
        casilla = html.split('name="seguimiento_incluir"')[1].split(">")[0]
        self.assertNotIn("checked", casilla)

    def test_sin_tareas_igual_hay_vista_previa(self):
        respuesta, _ = self.pedir_vista_previa(datos=salida(tareas=[]))
        self.assertContains(respuesta, 'name="total" value="2"')
        self.assertContains(respuesta, "Confirmar acuerdos")

    def test_la_fecha_la_envia_a_la_ia_para_resolver_el_viernes(self):
        with mock.patch("ia.views.timezone.localdate", return_value=date(2026, 11, 16)):
            _, simulado = self.pedir_vista_previa()
        self.assertIn("lunes 2026-11-16", simulado.call_args.args[1])

    def test_una_fecha_que_no_es_fecha_queda_vacia(self):
        datos = salida(tareas=[{"descripcion": "Algo", "responsable": None, "fecha_limite": "pronto"}])
        respuesta, _ = self.pedir_vista_previa(datos=datos)
        fila = respuesta.content.decode().split('name="t0-fecha_limite"')[1].split(">")[0]
        self.assertNotIn("value=", fila)

    def test_una_duracion_rara_se_acerca_a_la_mas_cercana_permitida(self):
        datos = salida(seguimiento={"asunto": "Otra", "duracion_min": 50})
        respuesta, _ = self.pedir_vista_previa(datos=datos)
        self.assertContains(respuesta, '<option value="45" selected>')

    def test_los_errores_de_la_ia_se_muestran_como_mensaje_y_no_se_guarda_nada(self):
        errores = (IaNoDisponible(), CupoDiarioAgotado(), EntradaInvalida("Escribe o dicta algo antes de continuar."))
        for error in errores:
            with mock.patch("ia.views.pedir_json", side_effect=error):
                respuesta = self.client.post(self.generar, {"notas": NOTAS})
            self.assertContains(respuesta, error.mensaje_usuario)
            self.assertContains(respuesta, 'role="alert"')
        self.assertEqual(AcuerdosReunion.objects.count(), 0)

    def test_solo_se_genera_para_reuniones_aprobadas(self):
        self.reunion.status = MeetingRequest.Status.PROPUESTA
        self.reunion.save()
        respuesta, simulado = self.pedir_vista_previa()
        self.assertContains(respuesta, "Solo las reuniones aprobadas tienen acuerdos.")
        simulado.assert_not_called()

    def test_no_se_vuelve_a_generar_si_ya_hay_acuerdos(self):
        self.confirmar_con()
        respuesta, simulado = self.pedir_vista_previa()
        self.assertContains(respuesta, "ya tiene sus acuerdos guardados")
        simulado.assert_not_called()


class IntegracionConGeminiTests(AcuerdosBase):
    """Atraviesa el cliente real de TR-80 con el envio por red simulado: salida invalida y tope diario."""

    def setUp(self):
        super().setUp()
        self.entrar(self.asistente)

    @mock.patch("ia.gemini._enviar")
    def test_flujo_completo_con_la_respuesta_de_gemini(self, enviar):
        enviar.return_value = respuesta_gemini(salida())
        respuesta = self.client.post(self.generar, {"notas": NOTAS})
        self.assertContains(respuesta, 'value="Enviar la versión final"')
        cuerpo = json.dumps(enviar.call_args.args[1], ensure_ascii=False)
        self.assertIn("Luis envía la versión final", cuerpo)
        self.assertEqual(UsoIA.objects.get(user=self.asistente).calls, 1)

    @mock.patch("ia.gemini._enviar")
    def test_una_salida_que_no_cumple_el_esquema_se_rechaza_con_un_mensaje(self, enviar):
        for mala in (
            {"resumen": "x", "tareas": "no es lista", "seguimiento": None},
            {"tareas": [], "seguimiento": None},
            {"resumen": "x", "tareas": [{"descripcion": "y" * 201, "responsable": None, "fecha_limite": None}],
             "seguimiento": None},
            "esto no es json",
        ):
            enviar.return_value = respuesta_gemini(mala)
            respuesta = self.client.post(self.generar, {"notas": NOTAS})
            self.assertContains(respuesta, 'role="alert"')
            self.assertNotContains(respuesta, "Confirmar acuerdos")
        self.assertEqual(AcuerdosReunion.objects.count(), 0)

    @override_settings(IA_LLAMADAS_POR_USUARIO_DIA=1)
    @mock.patch("ia.gemini._enviar")
    def test_respeta_el_tope_diario_por_usuario(self, enviar):
        enviar.return_value = respuesta_gemini(salida())
        self.client.post(self.generar, {"notas": NOTAS})
        respuesta = self.client.post(self.generar, {"notas": NOTAS})
        self.assertContains(respuesta, "límite diario")
        self.assertEqual(enviar.call_count, 1)

    @mock.patch("ia.gemini._enviar")
    def test_notas_de_mas_de_6000_caracteres_no_llegan_a_la_ia(self, enviar):
        respuesta = self.client.post(self.generar, {"notas": "a" * 6001})
        self.assertContains(respuesta, "supera el máximo de 6000")
        enviar.assert_not_called()

    @mock.patch("ia.gemini._enviar")
    def test_notas_vacias_no_llegan_a_la_ia(self, enviar):
        respuesta = self.client.post(self.generar, {"notas": "   "})
        self.assertContains(respuesta, "Escribe o dicta algo")
        enviar.assert_not_called()


class ConfirmacionTests(AcuerdosBase):
    def setUp(self):
        super().setUp()
        self.entrar(self.asistente)

    def test_guarda_notas_resumen_tareas_y_seguimiento(self):
        respuesta = self.confirmar_con()
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["HX-Redirect"], self.detalle)
        guardados = AcuerdosReunion.objects.get(request=self.reunion)
        self.assertEqual(guardados.notas, NOTAS)
        self.assertEqual(guardados.resumen, "Se revisó el contrato.")
        self.assertEqual(guardados.seguimiento_asunto, "Seguimiento del contrato")
        self.assertEqual(guardados.seguimiento_duracion, 45)
        self.assertEqual(guardados.created_by, self.asistente)
        tareas = list(guardados.tareas.values_list("descripcion", "responsable", "fecha_limite", "orden"))
        self.assertEqual(
            tareas,
            [("Enviar la versión final", "Luis", date(2026, 11, 20), 0), ("Confirmar el presupuesto", "Ana", None, 1)],
        )
        self.assertEqual([str(m) for m in get_messages(respuesta.wsgi_request)], ["Acuerdos guardados."])

    def test_las_filas_vacias_no_crean_tareas(self):
        self.confirmar_con()
        self.assertEqual(TareaReunion.objects.count(), 2)

    def test_se_puede_editar_el_resumen_y_las_tareas(self):
        self.confirmar_con(
            resumen="Resumen corregido por la asistente.",
            **{"t0-descripcion": "Enviar el contrato firmado", "t0-fecha_limite": "2026-11-27"},
        )
        guardados = AcuerdosReunion.objects.get()
        self.assertEqual(guardados.resumen, "Resumen corregido por la asistente.")
        primera = guardados.tareas.first()
        esperado = ("Enviar el contrato firmado", date(2026, 11, 27))
        self.assertEqual((primera.descripcion, primera.fecha_limite), esperado)

    def test_se_puede_quitar_una_tarea_desmarcandola(self):
        self.confirmar_con(**{"t1-incluir": None})
        self.assertEqual(list(TareaReunion.objects.values_list("descripcion", flat=True)), ["Enviar la versión final"])

    def test_se_puede_agregar_una_tarea_en_una_fila_vacia(self):
        self.confirmar_con(**{"t2-descripcion": "Reservar la sala", "t2-responsable": "Recepción"})
        self.assertEqual(TareaReunion.objects.count(), 3)
        self.assertEqual(TareaReunion.objects.get(descripcion="Reservar la sala").responsable, "Recepción")

    def test_sin_marcar_seguimiento_no_se_guarda(self):
        self.confirmar_con(seguimiento_incluir=None)
        guardados = AcuerdosReunion.objects.get()
        self.assertEqual((guardados.seguimiento_asunto, guardados.seguimiento_duracion), ("", None))
        self.assertFalse(guardados.tiene_seguimiento)

    def test_el_seguimiento_sin_duracion_usa_30_minutos(self):
        self.confirmar_con(seguimiento_duracion="")
        self.assertEqual(AcuerdosReunion.objects.get().seguimiento_duracion, 30)

    def test_una_tarea_con_responsable_pero_sin_descripcion_muestra_el_error_y_no_guarda(self):
        respuesta = self.confirmar_con(**{"t2-responsable": "Luis"})
        self.assertContains(respuesta, "Escribe qué hay que hacer")
        self.assertContains(respuesta, "Confirmar acuerdos")
        self.assertEqual(AcuerdosReunion.objects.count(), 0)
        self.assertEqual(TareaReunion.objects.count(), 0)

    def test_fecha_invalida_y_resumen_vacio_se_muestran_juntos(self):
        respuesta = self.confirmar_con(resumen="", **{"t0-fecha_limite": "31/31/2026"})
        html = respuesta.content.decode()
        self.assertIn("Este campo es obligatorio", html)
        self.assertIn("Introduzca una fecha válida", html)
        self.assertEqual(AcuerdosReunion.objects.count(), 0)

    def test_seguimiento_marcado_sin_asunto_es_un_error(self):
        respuesta = self.confirmar_con(seguimiento_asunto="")
        self.assertContains(respuesta, "Escribe el asunto del seguimiento.")
        self.assertEqual(AcuerdosReunion.objects.count(), 0)

    def test_al_corregir_un_error_se_conservan_las_notas_y_las_filas(self):
        respuesta = self.confirmar_con(resumen="")
        self.assertContains(respuesta, "Revisamos el contrato.")
        self.assertContains(respuesta, 'value="Luis"')
        self.assertContains(respuesta, 'name="total" value="4"')

    def test_sin_ninguna_tarea_se_guardan_solo_resumen_y_seguimiento(self):
        self.confirmar_con(**{"t0-incluir": None, "t1-incluir": None})
        self.assertEqual(AcuerdosReunion.objects.count(), 1)
        self.assertEqual(TareaReunion.objects.count(), 0)

    def test_datos_incompletos_o_manipulados_no_guardan_nada(self):
        casos = [
            dict(notas=""),
            dict(notas="a" * 6001),
            dict(total="0"),
            dict(total="abc"),
            dict(total="999"),
        ]
        for caso in casos:
            respuesta = self.confirmar_con(**caso)
            self.assertContains(respuesta, "No se recibieron los acuerdos", msg_prefix=str(caso))
        self.assertEqual(AcuerdosReunion.objects.count(), 0)

    def test_no_se_confirma_dos_veces(self):
        self.confirmar_con()
        respuesta = self.confirmar_con(resumen="Otro resumen")
        self.assertContains(respuesta, "ya tiene sus acuerdos guardados")
        self.assertEqual(AcuerdosReunion.objects.get().resumen, "Se revisó el contrato.")
        self.assertEqual(TareaReunion.objects.count(), 2)

    def test_solo_se_confirma_en_reuniones_aprobadas(self):
        self.reunion.status = MeetingRequest.Status.CANCELADA
        self.reunion.save()
        respuesta = self.confirmar_con()
        self.assertContains(respuesta, "Solo las reuniones aprobadas tienen acuerdos.")
        self.assertEqual(AcuerdosReunion.objects.count(), 0)

    def test_una_carrera_entre_dos_confirmaciones_deja_una_sola(self):
        with mock.patch("ia.views._motivo_para_no_registrar", return_value=None):
            self.confirmar_con()
            respuesta = self.confirmar_con(resumen="Segunda")
        self.assertContains(respuesta, "ya tiene sus acuerdos guardados")
        self.assertEqual(AcuerdosReunion.objects.count(), 1)
        self.assertEqual(AcuerdosReunion.objects.get().resumen, "Se revisó el contrato.")

    def test_confirmar_no_llama_a_la_ia(self):
        with mock.patch("ia.views.pedir_json") as simulado:
            self.confirmar_con()
        simulado.assert_not_called()


class PermisosTests(AcuerdosBase):
    def test_exigen_sesion_y_solo_aceptan_post(self):
        for url in (self.generar, self.confirmar):
            self.assertEqual(self.client.post(url, {}).status_code, 302)
        self.assertEqual(self.client.get(self.seguimiento).status_code, 302)
        self.entrar(self.asistente)
        for url in (self.generar, self.confirmar):
            self.assertEqual(self.client.get(url).status_code, 405)

    def test_un_usuario_ajeno_recibe_404_en_todo(self):
        guardados = AcuerdosReunion.objects.create(
            request=self.reunion, notas="n", resumen="r", seguimiento_asunto="s", created_by=self.asistente
        )
        TareaReunion.objects.create(acuerdos=guardados, descripcion="Tarea secreta")
        for ajeno in (self.sin_vinculo, self.otro_ejecutivo):
            self.entrar(ajeno)
            with mock.patch("ia.views.pedir_json") as simulado:
                self.assertEqual(self.client.post(self.generar, {"notas": NOTAS}).status_code, 404)
                self.assertEqual(self.confirmar_con().status_code, 404)
            simulado.assert_not_called()
            self.assertEqual(self.client.get(self.seguimiento).status_code, 404)
            self.assertEqual(self.client.get(self.detalle).status_code, 404)

    def test_el_ejecutivo_no_registra_acuerdos_ni_abre_el_seguimiento(self):
        self.entrar(self.ejecutivo)
        with mock.patch("ia.views.pedir_json") as simulado:
            self.assertEqual(self.client.post(self.generar, {"notas": NOTAS}).status_code, 403)
            self.assertEqual(self.confirmar_con().status_code, 403)
        simulado.assert_not_called()
        self.assertEqual(self.client.get(self.seguimiento).status_code, 403)
        self.assertEqual(AcuerdosReunion.objects.count(), 0)

    def test_un_ajeno_no_ve_las_tareas_en_ninguna_pantalla(self):
        guardados = AcuerdosReunion.objects.create(
            request=self.reunion, notas="n", resumen="Resumen privado", created_by=self.asistente
        )
        TareaReunion.objects.create(acuerdos=guardados, descripcion="Tarea secreta")
        self.entrar(self.sin_vinculo)
        self.assertNotContains(self.client.get(reverse("panel")), "Tarea secreta")
        self.assertEqual(self.client.get(self.detalle).status_code, 404)


class SeguimientoTests(AcuerdosBase):
    def setUp(self):
        super().setUp()
        self.entrar(self.asistente)

    def test_abre_el_formulario_precargado_sin_crear_nada(self):
        self.confirmar_con()
        antes = MeetingRequest.objects.count()
        respuesta = self.client.get(self.seguimiento)
        self.assertContains(respuesta, 'value="Seguimiento del contrato"')
        self.assertContains(respuesta, '<option value="45" selected>')
        self.assertContains(respuesta, f'<option value="{self.ejecutivo.pk}" selected>')
        self.assertContains(respuesta, 'value="Proveedor de Alicorp"')
        self.assertContains(respuesta, 'value="prov@alicorp.pe"')
        self.assertContains(respuesta, reverse("create_request"))
        self.assertEqual(MeetingRequest.objects.count(), antes)

    def test_enviar_el_formulario_precargado_crea_la_solicitud_con_las_reglas_de_siempre(self):
        self.confirmar_con()
        respuesta = self.client.get(self.seguimiento)
        self.assertContains(respuesta, 'type="submit">Crear solicitud')
        enviado = self.client.post(
            reverse("create_request"),
            {
                "executive": self.ejecutivo.pk,
                "title": "Seguimiento del contrato",
                "counterpart_name": "Proveedor de Alicorp",
                "counterpart_email": "prov@alicorp.pe",
                "duration_min": 45,
                "week": "2026-11-30",
                "notes": "",
            },
        )
        self.assertEqual(enviado.status_code, 302)
        nueva = MeetingRequest.objects.get(title="Seguimiento del contrato")
        self.assertEqual((nueva.executive, nueva.status, nueva.duration_min), (self.ejecutivo, "pendiente", 45))

    def test_sin_acuerdos_o_sin_seguimiento_propuesto_es_404(self):
        self.assertEqual(self.client.get(self.seguimiento).status_code, 404)
        self.confirmar_con(seguimiento_incluir=None)
        self.assertEqual(self.client.get(self.seguimiento).status_code, 404)

    def test_sin_duracion_guardada_usa_la_del_formulario(self):
        AcuerdosReunion.objects.create(
            request=self.reunion, notas="n", resumen="r", seguimiento_asunto="Seguimiento", created_by=self.asistente
        )
        self.assertContains(self.client.get(self.seguimiento), 'value="Seguimiento"')


class ModelosYEsquemaTests(SimpleTestCase):
    def test_representaciones(self):
        self.assertEqual(str(TareaReunion(descripcion="Enviar")), "Enviar")
        self.assertEqual(str(AcuerdosReunion(request_id=7)), "Acuerdos de la solicitud 7")

    def test_el_esquema_acepta_la_respuesta_esperada_y_rechaza_lo_demas(self):
        self.assertEqual(acuerdos.ESQUEMA.validar(salida())["tareas"][0]["responsable"], "Luis")
        for mala in (salida(resumen=""), salida(tareas=[{"descripcion": "x"}] * 16), salida(seguimiento="si")):
            with self.assertRaises(ValueError):
                acuerdos.ESQUEMA.validar(mala)

    def test_el_esquema_descarta_campos_que_no_declara(self):
        datos = salida(tareas=[{"descripcion": "x", "responsable": None, "fecha_limite": None, "prioridad": "alta"}])
        self.assertNotIn("prioridad", acuerdos.ESQUEMA.validar(datos)["tareas"][0])

    def test_la_instruccion_trae_la_fecha_de_hoy_en_espanol(self):
        self.assertIn("Hoy es miércoles 2026-11-18.", acuerdos.instruccion(date(2026, 11, 18)))
