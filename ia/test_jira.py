"""Pruebas del envio de tareas a Jira (HU-20). Nada sale a la red: la funcion de envio esta siempre simulada."""
import base64
import http.client
import json
import socket
from datetime import date, datetime, timezone as tz
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase, override_settings
from django.urls import reverse

from meetings.models import AssistantLink, MeetingRequest

from . import jira
from .models import AcuerdosReunion, TareaReunion

User = get_user_model()
TOKEN = "prueba-prueba-prueba-prueba"
CONFIG = dict(
    JIRA_SITE="equipo.atlassian.net",
    JIRA_EMAIL="mayerly@correo.pe",
    JIRA_TOKEN=TOKEN,
    JIRA_PROJECT="QDMDEMO",
    JIRA_ISSUE_TYPE="Tarea",
    JIRA_TIMEOUT=5,
)


def creada(clave="QDMDEMO-7"):
    return 201, {"id": "10001", "key": clave, "self": "https://equipo.atlassian.net/rest/api/3/issue/10001"}


@override_settings(**CONFIG)
class JiraBase(TestCase):
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
        self.reunion = self.crear_reunion(self.ejecutivo, "Revisar el contrato")
        self.ajena = self.crear_reunion(self.otro_ejecutivo, "Reunión reservada")
        self.tarea = self.crear_tarea(self.reunion, "Enviar la versión final", "Luis", date(2026, 11, 20))
        self.sin_fecha = self.crear_tarea(self.reunion, "Confirmar el presupuesto", "", None)
        self.secreta = self.crear_tarea(self.ajena, "Tarea secreta ajena", "Nadie", None)
        self.url = reverse("ia_tarea_jira", args=[self.tarea.pk])
        self.tablero = reverse("ia_tareas")

    def crear_reunion(self, ejecutivo, titulo):
        return MeetingRequest.objects.create(
            executive=ejecutivo,
            created_by=self.asistente,
            title=titulo,
            counterpart_name="Proveedor de Alicorp",
            status=MeetingRequest.Status.APROBADA,
            approved_start=datetime(2026, 11, 20, 15, 0, tzinfo=tz.utc),
            approved_end=datetime(2026, 11, 20, 16, 0, tzinfo=tz.utc),
        )

    def crear_tarea(self, reunion, descripcion, responsable, fecha):
        acuerdos, _ = AcuerdosReunion.objects.get_or_create(
            request=reunion, defaults=dict(notas="n", resumen="r", created_by=self.asistente)
        )
        return TareaReunion.objects.create(
            acuerdos=acuerdos, descripcion=descripcion, responsable=responsable, fecha_limite=fecha
        )

    def entrar(self, usuario):
        self.client.force_login(usuario)

    def mensajes(self, respuesta):
        return [str(m) for m in get_messages(respuesta.wsgi_request)]


class ConfiguracionTests(JiraBase):
    def test_configurado_exige_las_cuatro_variables(self):
        self.assertTrue(jira.configurado())
        for variable in ("JIRA_SITE", "JIRA_EMAIL", "JIRA_TOKEN", "JIRA_PROJECT"):
            with override_settings(**{variable: ""}):
                self.assertFalse(jira.configurado(), variable)
            with override_settings(**{variable: "   "}):
                self.assertFalse(jira.configurado(), variable)

    def test_el_sitio_debe_parecer_un_nombre_de_host(self):
        for malo in ("equipo.atlassian.net/ruta", "equipo atlassian", "http://x", "a@b.com", "x:80", "../x"):
            with override_settings(JIRA_SITE=malo):
                self.assertFalse(jira.configurado(), malo)
        with override_settings(JIRA_SITE="https://equipo.atlassian.net/"):
            self.assertTrue(jira.configurado())  # se tolera pegar la direccion completa

    def test_enlace_a_la_incidencia(self):
        self.assertEqual(jira.url_incidencia("QDMDEMO-7"), "https://equipo.atlassian.net/browse/QDMDEMO-7")
        self.assertEqual(jira.url_incidencia("no es una clave"), "")
        self.assertEqual(jira.url_incidencia(""), "")
        with override_settings(JIRA_SITE=""):
            self.assertEqual(jira.url_incidencia("QDMDEMO-7"), "")


class CuerpoTests(JiraBase):
    def test_trae_proyecto_tipo_etiqueta_resumen_descripcion_y_fecha(self):
        campos = jira.armar_cuerpo(self.tarea)["fields"]
        self.assertEqual(campos["project"], {"key": "QDMDEMO"})
        self.assertEqual(campos["issuetype"], {"name": "Tarea"})
        self.assertEqual(campos["labels"], ["quedamos-ia"])
        self.assertEqual(campos["summary"], "Enviar la versión final")
        self.assertEqual(campos["duedate"], "2026-11-20")
        texto = json.dumps(campos["description"], ensure_ascii=False)
        self.assertIn("Revisar el contrato", texto)
        self.assertIn("Proveedor de Alicorp", texto)
        self.assertIn("Responsable: Luis.", texto)
        self.assertIn("Fecha límite: 20/11/2026.", texto)
        self.assertEqual(campos["description"]["type"], "doc")
        self.assertEqual(campos["description"]["version"], 1)

    def test_sin_fecha_no_inventa_una(self):
        campos = jira.armar_cuerpo(self.sin_fecha)["fields"]
        self.assertNotIn("duedate", campos)
        self.assertNotIn("Fecha límite", json.dumps(campos["description"], ensure_ascii=False))
        self.assertNotIn("Responsable", json.dumps(campos["description"], ensure_ascii=False))

    def test_el_resumen_no_pasa_de_255_caracteres(self):
        self.tarea.descripcion = "x" * 300
        self.assertEqual(len(jira.armar_cuerpo(self.tarea)["fields"]["summary"]), 255)

    @override_settings(JIRA_ISSUE_TYPE="Task", JIRA_PROJECT=" QDMDEMO ")
    def test_el_tipo_y_el_proyecto_salen_de_la_configuracion(self):
        campos = jira.armar_cuerpo(self.tarea)["fields"]
        self.assertEqual((campos["issuetype"], campos["project"]), ({"name": "Task"}, {"key": "QDMDEMO"}))

    def test_sin_fecha_si_se_pide_omitirla(self):
        self.assertNotIn("duedate", jira.armar_cuerpo(self.tarea, con_fecha=False)["fields"])


class CrearIncidenciaTests(JiraBase):
    @mock.patch("ia.jira._enviar")
    def test_devuelve_la_clave(self, enviar):
        enviar.return_value = creada("QDMDEMO-12")
        self.assertEqual(jira.crear_incidencia(self.tarea), "QDMDEMO-12")
        enviar.assert_called_once()

    @mock.patch("ia.jira._enviar")
    def test_sin_configuracion_no_llama_a_jira(self, enviar):
        with override_settings(JIRA_TOKEN=""):
            with self.assertRaises(jira.JiraNoConfigurado):
                jira.crear_incidencia(self.tarea)
        enviar.assert_not_called()

    @mock.patch("ia.jira._enviar")
    def test_cada_fallo_tiene_su_mensaje_claro_y_menciona_el_csv(self, enviar):
        casos = {
            401: "credenciales",
            403: "permiso",
            404: "No se encontró el proyecto",
            429: "demasiadas solicitudes",
            500: "no está disponible",
            503: "no está disponible",
            400: "no aceptó la tarea",
            418: "no aceptó la tarea",
        }
        for estado, fragmento in casos.items():
            enviar.return_value = (estado, {"errorMessages": ["detalle interno de Jira"]})
            with self.assertRaises(jira.JiraError) as contexto:
                jira.crear_incidencia(self.tarea)
            mensaje = contexto.exception.mensaje_usuario
            self.assertIn(fragmento, mensaje, estado)
            self.assertIn("exportación CSV", mensaje, estado)
            self.assertNotIn("detalle interno", mensaje)

    @mock.patch("ia.jira._enviar")
    def test_un_201_sin_clave_valida_es_un_error(self, enviar):
        for raro in ({}, {"key": 5}, {"key": "esto no es una clave"}, {"key": "../../x"}):
            enviar.return_value = (201, raro)
            with self.assertRaises(jira.JiraError):
                jira.crear_incidencia(self.tarea)

    @mock.patch("ia.jira._enviar")
    def test_los_fallos_de_red_y_el_tiempo_de_espera_dan_un_mensaje_claro(self, enviar):
        fallos = (
            socket.timeout("timed out"),
            ConnectionResetError(),
            OSError("sin red"),
            http.client.BadStatusLine("x"),
        )
        for fallo in fallos:
            enviar.side_effect = fallo
            with self.assertRaises(jira.JiraError) as contexto:
                jira.crear_incidencia(self.tarea)
            self.assertIn("No se pudo conectar con Jira", contexto.exception.mensaje_usuario)
            self.assertIn("exportación CSV", contexto.exception.mensaje_usuario)

    @mock.patch("ia.jira._enviar")
    def test_si_el_proyecto_no_acepta_la_fecha_reintenta_sin_ella(self, enviar):
        enviar.side_effect = [(400, {"errors": {"duedate": "Field 'duedate' cannot be set."}}), creada("QDMDEMO-9")]
        self.assertEqual(jira.crear_incidencia(self.tarea), "QDMDEMO-9")
        self.assertIn("duedate", enviar.call_args_list[0].args[0]["fields"])
        self.assertNotIn("duedate", enviar.call_args_list[1].args[0]["fields"])
        self.assertIn("20/11/2026", json.dumps(enviar.call_args_list[1].args[0], ensure_ascii=False))

    @mock.patch("ia.jira._enviar")
    def test_un_400_por_otra_causa_no_se_reintenta(self, enviar):
        enviar.return_value = (400, {"errors": {"issuetype": "valor no valido"}})
        with self.assertRaises(jira.JiraError):
            jira.crear_incidencia(self.tarea)
        enviar.assert_called_once()

    @mock.patch("ia.jira._enviar")
    def test_un_400_de_fecha_en_una_tarea_sin_fecha_no_se_reintenta(self, enviar):
        enviar.return_value = (400, {"errors": {"duedate": "x"}})
        with self.assertRaises(jira.JiraError):
            jira.crear_incidencia(self.sin_fecha)
        enviar.assert_called_once()


class EnvioPorRedTests(JiraBase):
    """Prueba la funcion que sale a la red con la conexion simulada: cabeceras, ruta, cuerpo y lectura."""

    def conexion(self, estado=201, cuerpo=b'{"key": "QDMDEMO-3"}'):
        respuesta = mock.Mock(status=estado)
        respuesta.read.return_value = cuerpo
        conexion = mock.Mock()
        conexion.getresponse.return_value = respuesta
        return conexion

    def test_usa_https_al_sitio_configurado_con_autenticacion_basica_en_cabecera(self):
        conexion = self.conexion()
        with mock.patch("ia.jira.http.client.HTTPSConnection", return_value=conexion) as clase:
            estado, datos = jira._enviar({"fields": {}})
        clase.assert_called_once_with("equipo.atlassian.net", timeout=5)
        self.assertEqual((estado, datos), (201, {"key": "QDMDEMO-3"}))
        metodo, ruta = conexion.request.call_args.args[:2]
        self.assertEqual((metodo, ruta), ("POST", "/rest/api/3/issue"))
        self.assertNotIn(TOKEN, ruta)
        cabeceras = conexion.request.call_args.kwargs["headers"]
        esperado = base64.b64encode(f"mayerly@correo.pe:{TOKEN}".encode()).decode()
        self.assertEqual(cabeceras["Authorization"], f"Basic {esperado}")
        self.assertEqual(cabeceras["Content-Type"], "application/json")
        conexion.close.assert_called_once()

    def test_una_respuesta_que_no_es_json_o_no_es_objeto_se_trata_como_vacia(self):
        for crudo in (b"<html>error</html>", b"[1, 2]", b""):
            with mock.patch("ia.jira.http.client.HTTPSConnection", return_value=self.conexion(500, crudo)):
                self.assertEqual(jira._enviar({}), (500, {}))

    def test_cierra_la_conexion_aunque_falle(self):
        conexion = self.conexion()
        conexion.request.side_effect = socket.timeout()
        with mock.patch("ia.jira.http.client.HTTPSConnection", return_value=conexion):
            with self.assertRaises(socket.timeout):
                jira._enviar({})
        conexion.close.assert_called_once()


class EnviarATareaTests(JiraBase):
    def setUp(self):
        super().setUp()
        self.entrar(self.asistente)

    @mock.patch("ia.jira._enviar")
    def test_envia_y_guarda_la_clave(self, enviar):
        enviar.return_value = creada("QDMDEMO-7")
        respuesta = self.client.post(self.url)
        self.assertRedirects(respuesta, self.tablero, fetch_redirect_response=False)
        self.tarea.refresh_from_db()
        self.assertEqual(self.tarea.jira_key, "QDMDEMO-7")
        self.assertTrue(self.tarea.enviada_a_jira)
        self.assertEqual(self.mensajes(respuesta), ["Tarea enviada a Jira: QDMDEMO-7."])

    @mock.patch("ia.jira._enviar")
    def test_un_segundo_intento_no_crea_otra_incidencia(self, enviar):
        enviar.return_value = creada("QDMDEMO-7")
        self.client.post(self.url)
        respuesta = self.client.post(self.url)
        self.assertEqual(enviar.call_count, 1)
        self.assertEqual(self.mensajes(respuesta)[-1], "Esta tarea ya está en Jira (QDMDEMO-7).")
        self.tarea.refresh_from_db()
        self.assertEqual(self.tarea.jira_key, "QDMDEMO-7")

    @mock.patch("ia.jira._enviar")
    def test_ante_cualquier_fallo_la_tarea_no_queda_marcada_y_se_puede_reintentar(self, enviar):
        for fallo in ((401, {}), (403, {}), (429, {}), (500, {}), socket.timeout("timed out")):
            if isinstance(fallo, Exception):
                enviar.side_effect = fallo
            else:
                enviar.side_effect = None
                enviar.return_value = fallo
            respuesta = self.client.post(self.url)
            self.assertRedirects(respuesta, self.tablero, fetch_redirect_response=False)
            self.tarea.refresh_from_db()
            self.assertEqual(self.tarea.jira_key, "", fallo)
            self.assertIn("exportación CSV", self.mensajes(respuesta)[-1])
        enviar.side_effect = None
        enviar.return_value = creada("QDMDEMO-8")
        self.client.post(self.url)
        self.tarea.refresh_from_db()
        self.assertEqual(self.tarea.jira_key, "QDMDEMO-8")

    @mock.patch("ia.jira._enviar")
    def test_el_token_no_aparece_en_mensajes_ni_respuestas(self, enviar):
        enviar.return_value = (401, {"message": f"token {TOKEN} invalido"})
        respuesta = self.client.post(self.url, follow=True)
        self.assertNotContains(respuesta, TOKEN)
        self.assertNotIn(TOKEN, " ".join(self.mensajes(respuesta)))
        self.assertNotContains(self.client.get(self.tablero), TOKEN)

    def test_el_token_no_se_registra(self):
        with self.assertLogs("ia", level="DEBUG") as registro:
            with mock.patch("ia.jira._enviar", return_value=(401, {"message": TOKEN})):
                self.client.post(self.url)
            with mock.patch("ia.jira._enviar", side_effect=OSError(f"fallo con {TOKEN}")):
                self.client.post(self.url)
        self.assertTrue(registro.output)
        self.assertNotIn(TOKEN, "\n".join(registro.output))

    @mock.patch("ia.jira._enviar")
    def test_sin_configuracion_no_llama_a_jira_y_avisa(self, enviar):
        with override_settings(JIRA_SITE=""):
            respuesta = self.client.post(self.url)
        enviar.assert_not_called()
        self.assertIn("exportación CSV", self.mensajes(respuesta)[0])
        self.tarea.refresh_from_db()
        self.assertEqual(self.tarea.jira_key, "")

    @mock.patch("ia.jira._enviar")
    def test_vuelve_al_tablero_con_el_mismo_filtro(self, enviar):
        enviar.return_value = creada()
        respuesta = self.client.post(self.url, {"estado": "pendiente", "reunion": str(self.reunion.pk)})
        self.assertEqual(respuesta["Location"], f"{self.tablero}?estado=pendiente&reunion={self.reunion.pk}")

    @mock.patch("ia.jira._enviar")
    def test_envia_la_fecha_y_el_responsable_de_la_tarea_correcta(self, enviar):
        enviar.return_value = creada()
        self.client.post(self.url)
        cuerpo = enviar.call_args.args[0]["fields"]
        self.assertEqual(cuerpo["summary"], "Enviar la versión final")
        self.assertEqual(cuerpo["duedate"], "2026-11-20")


class PermisosJiraTests(JiraBase):
    def test_exige_sesion_y_solo_acepta_post(self):
        self.assertEqual(self.client.post(self.url).status_code, 302)
        self.entrar(self.asistente)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    @mock.patch("ia.jira._enviar")
    def test_una_tarea_ajena_da_404_y_no_llama_a_jira(self, enviar):
        casos = [(self.sin_vinculo, self.tarea), (self.asistente, self.secreta), (self.ejecutivo, self.secreta)]
        for usuario, tarea in casos:
            self.entrar(usuario)
            self.assertEqual(self.client.post(reverse("ia_tarea_jira", args=[tarea.pk])).status_code, 404)
        enviar.assert_not_called()

    @mock.patch("ia.jira._enviar")
    def test_el_ejecutivo_no_envia_a_jira(self, enviar):
        self.entrar(self.ejecutivo)
        self.assertEqual(self.client.post(self.url).status_code, 403)
        enviar.assert_not_called()
        self.tarea.refresh_from_db()
        self.assertEqual(self.tarea.jira_key, "")

    @mock.patch("ia.jira._enviar")
    def test_una_tarea_que_no_existe_da_404(self, enviar):
        self.entrar(self.asistente)
        self.assertEqual(self.client.post(reverse("ia_tarea_jira", args=[99999])).status_code, 404)
        enviar.assert_not_called()


class BotonTests(JiraBase):
    def test_la_asistente_ve_el_boton_si_hay_configuracion(self):
        self.entrar(self.asistente)
        respuesta = self.client.get(self.tablero)
        self.assertContains(respuesta, "Enviar a Jira", count=2)  # una por tarea
        self.assertContains(respuesta, self.url)

    def test_sin_configuracion_no_hay_boton_y_queda_el_csv(self):
        self.entrar(self.asistente)
        for variable in ("JIRA_SITE", "JIRA_EMAIL", "JIRA_TOKEN", "JIRA_PROJECT"):
            with override_settings(**{variable: ""}):
                respuesta = self.client.get(self.tablero)
                self.assertNotContains(respuesta, "Enviar a Jira", msg_prefix=variable)
                self.assertContains(respuesta, "Exportar CSV para Jira", msg_prefix=variable)

    def test_el_ejecutivo_no_ve_el_boton(self):
        self.entrar(self.ejecutivo)
        self.assertNotContains(self.client.get(self.tablero), "Enviar a Jira")

    def test_una_tarea_enviada_muestra_su_clave_con_enlace_y_sin_boton(self):
        self.tarea.jira_key = "QDMDEMO-7"
        self.tarea.save()
        self.entrar(self.asistente)
        respuesta = self.client.get(self.tablero)
        self.assertContains(respuesta, 'href="https://equipo.atlassian.net/browse/QDMDEMO-7"')
        self.assertContains(respuesta, "En Jira:")
        self.assertContains(respuesta, "Enviar a Jira", count=1)  # solo la tarea que falta

    def test_la_clave_enviada_se_ve_aunque_ya_no_haya_configuracion_pero_sin_enlace(self):
        self.tarea.jira_key = "QDMDEMO-7"
        self.tarea.save()
        self.entrar(self.ejecutivo)
        with override_settings(JIRA_SITE=""):
            respuesta = self.client.get(self.tablero)
        self.assertContains(respuesta, "En Jira: QDMDEMO-7")
        self.assertNotContains(respuesta, "/browse/")

    def test_el_enlace_externo_no_filtra_el_origen(self):
        self.tarea.jira_key = "QDMDEMO-7"
        self.tarea.save()
        self.entrar(self.asistente)
        self.assertContains(self.client.get(self.tablero), 'rel="noopener noreferrer"')

    def test_una_tarea_sin_clave_no_esta_enviada(self):
        self.assertFalse(self.tarea.enviada_a_jira)
