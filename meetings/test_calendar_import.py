"""Pruebas de la importación de disponibilidad desde un archivo .ics (TR-14)."""
from datetime import date, datetime, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.urls import reverse

from .calendar_import import ICSError, MAX_BYTES, decode_ics, free_blocks, parse_ics, week_window
from .models import Availability
from .test_proposal_views import ProposalViewBase

LIMA = ZoneInfo("America/Lima")
LUNES = date(2026, 10, 26)  # semana del 26/10 al 01/11


def calendario(*eventos):
    cuerpo = "\r\n".join(eventos)
    return f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Prueba//ES\r\n{cuerpo}\r\nEND:VCALENDAR\r\n"


def evento(*lineas):
    return "BEGIN:VEVENT\r\n" + "\r\n".join(lineas) + "\r\nEND:VEVENT"


def leer(texto):
    inicio, fin = week_window(LUNES, LIMA)
    return parse_ics(texto, LIMA, inicio, fin)


def local(dia, hora, minuto=0):
    return datetime(2026, 10, 26 + dia, hora, minuto, tzinfo=LIMA)


def intervalos(resultado):
    return sorted((a.astimezone(LIMA), b.astimezone(LIMA)) for a, b in resultado.busy)


class LecturaDeEventosTests(SimpleTestCase):
    def test_evento_en_utc_se_convierte_a_la_hora_de_lima(self):
        r = leer(calendario(evento("UID:a", "DTSTART:20261027T150000Z", "DTEND:20261027T160000Z")))
        self.assertEqual(intervalos(r), [(local(1, 10), local(1, 11))])

    def test_evento_con_zona_horaria_propia(self):
        r = leer(calendario(evento("UID:a", "DTSTART;TZID=America/New_York:20261027T110000", "DTEND;TZID=America/New_York:20261027T120000")))
        self.assertEqual(intervalos(r), [(local(1, 10), local(1, 11))])

    def test_zona_de_windows_se_reconoce(self):
        r = leer(calendario(evento("UID:a", "DTSTART;TZID=SA Pacific Standard Time:20261027T100000", "DTEND;TZID=SA Pacific Standard Time:20261027T110000")))
        self.assertEqual(intervalos(r), [(local(1, 10), local(1, 11))])
        self.assertEqual(r.unknown_zones, set())

    def test_zona_desconocida_usa_lima_y_se_informa(self):
        r = leer(calendario(evento("UID:a", "DTSTART;TZID=Zona Inventada:20261027T100000", "DTEND;TZID=Zona Inventada:20261027T110000")))
        self.assertEqual(intervalos(r), [(local(1, 10), local(1, 11))])
        self.assertEqual(r.unknown_zones, {"Zona Inventada"})

    def test_evento_sin_zona_se_toma_como_hora_local(self):
        r = leer(calendario(evento("UID:a", "DTSTART:20261027T090000", "DTEND:20261027T093000")))
        self.assertEqual(intervalos(r), [(local(1, 9), local(1, 9, 30))])

    def test_duracion_en_lugar_de_fin(self):
        r = leer(calendario(evento("UID:a", "DTSTART:20261027T090000", "DURATION:PT1H30M")))
        self.assertEqual(intervalos(r), [(local(1, 9), local(1, 10, 30))])

    def test_evento_de_dia_completo_ocupa_todo_el_dia(self):
        r = leer(calendario(evento("UID:a", "DTSTART;VALUE=DATE:20261028", "DTEND;VALUE=DATE:20261029")))
        self.assertEqual(intervalos(r), [(local(2, 0), local(3, 0))])

    def test_dia_completo_marcado_como_libre_no_ocupa(self):
        r = leer(calendario(evento("UID:a", "DTSTART;VALUE=DATE:20261028", "DTEND;VALUE=DATE:20261029", "TRANSP:TRANSPARENT")))
        self.assertEqual(r.busy, [])

    def test_evento_cancelado_no_ocupa(self):
        r = leer(calendario(evento("UID:a", "DTSTART:20261027T090000", "DTEND:20261027T100000", "STATUS:CANCELLED")))
        self.assertEqual(r.busy, [])

    def test_evento_fuera_de_la_semana_se_ignora(self):
        r = leer(calendario(evento("UID:a", "DTSTART:20261104T090000", "DTEND:20261104T100000")))
        self.assertEqual(r.busy, [])
        self.assertEqual(r.events, 1)

    def test_evento_que_cruza_la_medianoche_del_domingo_cuenta_en_la_semana(self):
        r = leer(calendario(evento("UID:a", "DTSTART:20261101T230000", "DTEND:20261102T010000")))
        self.assertEqual(len(r.busy), 1)

    def test_evento_sin_fin_ni_duracion_no_ocupa_tiempo(self):
        r = leer(calendario(evento("UID:a", "DTSTART:20261027T090000")))
        self.assertEqual(r.busy, [])

    def test_lineas_plegadas_y_parametros_con_comillas(self):
        texto = calendario(evento(
            "UID:a", "SUMMARY:Reunion con un titulo muy largo que\r\n  continua en otra linea",
            'DTSTART;TZID="America/Lima":20261027T090000', "DTEND;TZID=America/Lima:20261027T100000",
        ))
        self.assertEqual(intervalos(leer(texto)), [(local(1, 9), local(1, 10))])

    def test_un_evento_ilegible_se_omite_y_se_cuenta(self):
        texto = calendario(
            evento("UID:a", "DTSTART:no-es-una-fecha", "DTEND:20261027T100000"),
            evento("UID:b", "DTSTART:20261027T090000", "DTEND:20261027T100000"),
        )
        r = leer(texto)
        self.assertEqual((r.skipped, len(r.busy)), (1, 1))

    def test_las_alarmas_y_zonas_del_archivo_no_se_confunden_con_eventos(self):
        texto = calendario(
            "BEGIN:VTIMEZONE\r\nTZID:America/Lima\r\nBEGIN:STANDARD\r\nDTSTART:19700101T000000\r\nTZOFFSETFROM:-0500\r\nTZOFFSETTO:-0500\r\nEND:STANDARD\r\nEND:VTIMEZONE",
            evento("UID:a", "DTSTART:20261027T090000", "DTEND:20261027T100000", "BEGIN:VALARM", "TRIGGER:-PT15M", "ACTION:DISPLAY", "END:VALARM"),
        )
        r = leer(texto)
        self.assertEqual((r.events, intervalos(r)), (1, [(local(1, 9), local(1, 10))]))


class RecurrenciasTests(SimpleTestCase):
    def test_serie_semanal_con_dias_y_sin_fin(self):
        texto = calendario(evento("UID:a", "DTSTART;TZID=America/Lima:20260105T090000", "DTEND;TZID=America/Lima:20260105T100000", "RRULE:FREQ=WEEKLY;BYDAY=MO,WE"))
        self.assertEqual(intervalos(leer(texto)), [(local(0, 9), local(0, 10)), (local(2, 9), local(2, 10))])

    def test_serie_semanal_con_intervalo_de_dos_semanas(self):
        # 05/01/2026 + 2k semanas: el 26/10/2026 esta a 42 semanas, es decir, cae en la serie
        texto = calendario(evento("UID:a", "DTSTART;TZID=America/Lima:20260105T090000", "DTEND;TZID=America/Lima:20260105T100000", "RRULE:FREQ=WEEKLY;INTERVAL=2"))
        self.assertEqual(len(leer(texto).busy), 1)
        otra = calendario(evento("UID:a", "DTSTART;TZID=America/Lima:20260112T090000", "DTEND;TZID=America/Lima:20260112T100000", "RRULE:FREQ=WEEKLY;INTERVAL=2"))
        self.assertEqual(leer(otra).busy, [])

    def test_serie_con_count_que_ya_termino(self):
        texto = calendario(evento("UID:a", "DTSTART;TZID=America/Lima:20260105T090000", "DTEND;TZID=America/Lima:20260105T100000", "RRULE:FREQ=WEEKLY;COUNT=3"))
        self.assertEqual(leer(texto).busy, [])

    def test_serie_con_until_antes_de_la_semana(self):
        texto = calendario(evento("UID:a", "DTSTART;TZID=America/Lima:20260105T090000", "DTEND;TZID=America/Lima:20260105T100000", "RRULE:FREQ=WEEKLY;UNTIL=20261001T000000Z"))
        self.assertEqual(leer(texto).busy, [])

    def test_serie_diaria_con_filtro_de_dias(self):
        texto = calendario(evento("UID:a", "DTSTART;TZID=America/Lima:20261026T080000", "DTEND;TZID=America/Lima:20261026T083000", "RRULE:FREQ=DAILY;BYDAY=MO,TU,WE,TH,FR"))
        self.assertEqual(len(leer(texto).busy), 5)

    def test_serie_mensual_por_dia_del_mes(self):
        texto = calendario(evento("UID:a", "DTSTART;TZID=America/Lima:20260128T090000", "DTEND;TZID=America/Lima:20260128T100000", "RRULE:FREQ=MONTHLY"))
        self.assertEqual(intervalos(leer(texto)), [(local(2, 9), local(2, 10))])

    def test_serie_anual(self):
        texto = calendario(evento("UID:a", "DTSTART;TZID=America/Lima:20251028T090000", "DTEND;TZID=America/Lima:20251028T100000", "RRULE:FREQ=YEARLY"))
        self.assertEqual(intervalos(leer(texto)), [(local(2, 9), local(2, 10))])

    def test_fecha_excluida_no_cuenta(self):
        texto = calendario(evento(
            "UID:a", "DTSTART;TZID=America/Lima:20260105T090000", "DTEND;TZID=America/Lima:20260105T100000",
            "RRULE:FREQ=WEEKLY;BYDAY=MO,WE", "EXDATE;TZID=America/Lima:20261026T090000",
        ))
        self.assertEqual(intervalos(leer(texto)), [(local(2, 9), local(2, 10))])

    def test_instancia_modificada_reemplaza_a_la_de_la_serie(self):
        texto = calendario(
            evento("UID:a", "DTSTART;TZID=America/Lima:20260105T090000", "DTEND;TZID=America/Lima:20260105T100000", "RRULE:FREQ=WEEKLY"),
            evento("UID:a", "RECURRENCE-ID;TZID=America/Lima:20261026T090000", "DTSTART;TZID=America/Lima:20261026T150000", "DTEND;TZID=America/Lima:20261026T160000"),
        )
        self.assertEqual(intervalos(leer(texto)), [(local(0, 15), local(0, 16))])

    def test_repeticion_no_interpretable_cuenta_solo_la_primera_fecha_y_se_informa(self):
        texto = calendario(evento("UID:a", "DTSTART;TZID=America/Lima:20261027T090000", "DTEND;TZID=America/Lima:20261027T100000", "RRULE:FREQ=MONTHLY;BYDAY=1TU"))
        r = leer(texto)
        self.assertEqual((r.unsupported, len(r.busy)), (1, 1))

    def test_repeticion_por_horas_no_se_interpreta(self):
        texto = calendario(evento("UID:a", "DTSTART;TZID=America/Lima:20261027T090000", "DTEND;TZID=America/Lima:20261027T100000", "RRULE:FREQ=HOURLY"))
        self.assertEqual(leer(texto).unsupported, 1)

    def test_un_archivo_con_demasiadas_repeticiones_no_consume_el_servidor(self):
        serie = evento("UID:a", "DTSTART;TZID=America/Lima:20000103T090000", "DTEND;TZID=America/Lima:20000103T100000", "RRULE:FREQ=DAILY")
        with mock.patch("meetings.calendar_import.MAX_TOTAL_STEPS", 50):
            r = leer(calendario(serie, serie.replace("UID:a", "UID:b")))
        self.assertEqual(r.unsupported, 2)

    def test_regla_con_valores_invalidos_no_rompe(self):
        texto = calendario(evento("UID:a", "DTSTART;TZID=America/Lima:20261027T090000", "DTEND;TZID=America/Lima:20261027T100000", "RRULE:FREQ=WEEKLY;INTERVAL=0"))
        self.assertEqual(leer(texto).unsupported, 1)


class ArchivosInvalidosTests(SimpleTestCase):
    def test_texto_que_no_es_un_calendario(self):
        with self.assertRaisesMessage(ICSError, "no parece un calendario"):
            leer("esto es solo un texto cualquiera")

    def test_calendario_sin_eventos(self):
        with self.assertRaisesMessage(ICSError, "no tiene eventos"):
            leer("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nEND:VCALENDAR\r\n")

    def test_ningun_evento_legible(self):
        with self.assertRaisesMessage(ICSError, "ningún evento"):
            leer(calendario(evento("UID:a", "DTSTART:basura", "DTEND:basura")))

    def test_archivo_vacio(self):
        with self.assertRaisesMessage(ICSError, "vacío"):
            decode_ics(b"   \n")

    def test_archivo_binario(self):
        with self.assertRaisesMessage(ICSError, "no es un calendario de texto"):
            decode_ics(b"\x89PNG\r\n\x1a\n\x00\x00\x00")

    def test_archivo_demasiado_grande(self):
        with self.assertRaisesMessage(ICSError, "supera el máximo"):
            decode_ics(b"A" * (MAX_BYTES + 1))

    def test_codificacion_latin1_se_lee(self):
        texto = decode_ics("BEGIN:VCALENDAR\nSUMMARY:Reunión\nEND:VCALENDAR".encode("cp1252"))
        self.assertIn("Reunión", texto)

    def test_demasiados_eventos(self):
        muchos = calendario(*[evento(f"UID:{i}", "DTSTART:20261027T090000", "DTEND:20261027T100000") for i in range(5001)])
        with self.assertRaisesMessage(ICSError, "más de 5000 eventos"):
            leer(muchos)


class HorariosLibresTests(SimpleTestCase):
    def libres(self, *eventos):
        return free_blocks(leer(calendario(*eventos)).busy, LUNES, LIMA)

    def test_sin_eventos_en_la_semana_todo_lunes_a_viernes_queda_libre(self):
        bloques = self.libres(evento("UID:a", "DTSTART:20261201T090000", "DTEND:20261201T100000"))
        self.assertEqual(len(bloques), 5 * 14)
        self.assertTrue(all(valor == 1 for valor in bloques.values()))

    def test_el_fin_de_semana_no_se_marca(self):
        bloques = self.libres(evento("UID:a", "DTSTART:20261201T090000", "DTEND:20261201T100000"))
        self.assertFalse(any(clave.startswith(("5-", "6-")) for clave in bloques))

    def test_un_evento_de_una_hora_quita_solo_ese_bloque(self):
        bloques = self.libres(evento("UID:a", "DTSTART:20261027T100000", "DTEND:20261027T110000"))
        self.assertNotIn("1-10", bloques)
        self.assertIn("1-9", bloques)
        self.assertIn("1-11", bloques)

    def test_un_evento_que_empieza_y_termina_a_mitad_de_hora_quita_los_dos_bloques(self):
        bloques = self.libres(evento("UID:a", "DTSTART:20261027T103000", "DTEND:20261027T113000"))
        self.assertNotIn("1-10", bloques)
        self.assertNotIn("1-11", bloques)
        self.assertIn("1-12", bloques)

    def test_un_evento_que_termina_justo_al_inicio_del_bloque_no_lo_quita(self):
        bloques = self.libres(evento("UID:a", "DTSTART:20261027T090000", "DTEND:20261027T100000"))
        self.assertNotIn("1-9", bloques)
        self.assertIn("1-10", bloques)

    def test_un_dia_completo_ocupado_no_deja_bloques_ese_dia(self):
        bloques = self.libres(evento("UID:a", "DTSTART;VALUE=DATE:20261028", "DTEND;VALUE=DATE:20261029"))
        self.assertFalse(any(clave.startswith("2-") for clave in bloques))
        self.assertEqual(len(bloques), 4 * 14)

    def test_calendario_totalmente_ocupado_no_deja_nada(self):
        eventos = [evento(f"UID:{d}", f"DTSTART:2026102{6 + d}T080000", f"DTEND:2026102{6 + d}T220000") for d in range(4)]
        eventos.append(evento("UID:v", "DTSTART:20261030T080000", "DTEND:20261030T220000"))
        self.assertEqual(self.libres(*eventos), {})


class VistaDeImportacionTests(ProposalViewBase):
    def url(self):
        return reverse("import_executive_calendar", args=[self.req.pk])

    def archivo(self, texto, nombre="calendario.ics"):
        return SimpleUploadedFile(nombre, texto.encode("utf-8") if isinstance(texto, str) else texto, content_type="text/calendar")

    def importar(self, texto, nombre="calendario.ics", usuario=None):
        self.login(usuario or self.asis)
        return self.client.post(self.url(), {"archivo": self.archivo(texto, nombre)})

    def mensajes(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]

    def disponibilidad(self):
        return Availability.objects.filter(request=self.req, party="ejecutivo").first()

    def test_importar_guarda_la_disponibilidad_del_ejecutivo(self):
        r = self.importar(calendario(evento("UID:a", "DTSTART:20261027T150000Z", "DTEND:20261027T160000Z")))
        self.assertRedirects(r, reverse("request_detail", args=[self.req.pk]))
        bloques = self.disponibilidad().blocks
        self.assertNotIn("1-10", bloques)
        self.assertIn("1-9", bloques)
        self.assertEqual(len(bloques), 5 * 14 - 1)
        self.assertIn("Importamos el calendario", self.mensajes(r)[0])

    def test_reemplaza_la_disponibilidad_anterior(self):
        Availability.objects.create(request=self.req, party="ejecutivo", blocks={"6-20": 2})
        self.importar(calendario(evento("UID:a", "DTSTART:20261027T150000Z", "DTEND:20261027T160000Z")))
        self.assertNotIn("6-20", self.disponibilidad().blocks)

    def test_no_se_guardan_titulos_ni_detalles_de_los_eventos(self):
        self.importar(calendario(evento(
            "UID:a", "SUMMARY:Cita medica privada", "DESCRIPTION:Detalle confidencial", "LOCATION:Clinica Central",
            "ATTENDEE:mailto:secreto@correo.com", "DTSTART:20261027T150000Z", "DTEND:20261027T160000Z",
        )))
        guardado = str(Availability.objects.filter(request=self.req).values())
        for texto in ("Cita medica", "confidencial", "Clinica", "secreto@"):
            self.assertNotIn(texto, guardado)

    def test_el_archivo_no_se_escribe_en_disco(self):
        from django.conf import settings
        antes = {p.name for p in settings.BASE_DIR.iterdir()}
        self.importar(calendario(evento("UID:a", "DTSTART:20261027T150000Z", "DTEND:20261027T160000Z")))
        self.assertEqual({p.name for p in settings.BASE_DIR.iterdir()}, antes)

    def test_archivo_invalido_muestra_un_mensaje_claro_y_no_cambia_nada(self):
        Availability.objects.create(request=self.req, party="ejecutivo", blocks={"0-9": 1})
        r = self.importar("esto no es un calendario")
        self.assertIn("no parece un calendario", self.mensajes(r)[0])
        self.assertEqual(self.disponibilidad().blocks, {"0-9": 1})

    def test_extension_incorrecta(self):
        r = self.importar(calendario(evento("UID:a", "DTSTART:20261027T150000Z", "DTEND:20261027T160000Z")), nombre="calendario.txt")
        self.assertIn("extensión .ics", self.mensajes(r)[0])
        self.assertIsNone(self.disponibilidad())

    def test_archivo_demasiado_grande_se_rechaza(self):
        r = self.importar(b"A" * (MAX_BYTES + 10))
        self.assertIn("supera el máximo", self.mensajes(r)[0])
        self.assertIsNone(self.disponibilidad())

    def test_sin_archivo(self):
        self.login(self.asis)
        r = self.client.post(self.url(), {})
        self.assertIn("Elige un archivo", self.mensajes(r)[0])

    def test_calendario_totalmente_ocupado_no_guarda(self):
        eventos = [evento(f"UID:{d}", f"DTSTART:2026102{6 + d}T080000", f"DTEND:2026102{6 + d}T220000") for d in range(4)]
        eventos.append(evento("UID:v", "DTSTART:20261030T080000", "DTEND:20261030T220000"))
        r = self.importar(calendario(*eventos))
        self.assertIn("no queda ningún horario libre", self.mensajes(r)[0])
        self.assertIsNone(self.disponibilidad())

    def test_se_informa_lo_que_no_se_pudo_interpretar(self):
        r = self.importar(calendario(evento("UID:a", "DTSTART;TZID=America/Lima:20261027T090000", "DTEND;TZID=America/Lima:20261027T100000", "RRULE:FREQ=HOURLY")))
        self.assertTrue(any("no sabemos interpretar" in m for m in self.mensajes(r)))

    def test_el_ejecutivo_no_puede_importar_porque_la_coordinacion_es_de_la_asistente(self):
        r = self.importar(calendario(evento("UID:a", "DTSTART:20261027T150000Z", "DTEND:20261027T160000Z")), usuario=self.ejec)
        self.assertEqual(r.status_code, 403)
        self.assertIsNone(self.disponibilidad())

    def test_una_asistente_no_vinculada_recibe_404(self):
        r = self.importar(calendario(evento("UID:a", "DTSTART:20261027T150000Z", "DTEND:20261027T160000Z")), usuario=self.otra)
        self.assertEqual(r.status_code, 404)
        self.assertIsNone(self.disponibilidad())

    def test_sin_iniciar_sesion_redirige_al_acceso(self):
        r = self.client.post(self.url(), {"archivo": self.archivo(calendario(evento("UID:a", "DTSTART:20261027T150000Z", "DTEND:20261027T160000Z")))})
        self.assertEqual(r.status_code, 302)
        self.assertIn("/acceso/", r["Location"])

    def test_solo_acepta_post(self):
        self.login(self.asis)
        self.assertEqual(self.client.get(self.url()).status_code, 405)

    def test_una_solicitud_aprobada_ya_no_recibe_importaciones(self):
        self.req.status = "aprobada"
        self.req.save(update_fields=["status"])
        r = self.importar(calendario(evento("UID:a", "DTSTART:20261027T150000Z", "DTEND:20261027T160000Z")))
        self.assertIn("ya no recibe disponibilidad", self.mensajes(r)[0])
        self.assertIsNone(self.disponibilidad())

    def test_la_pantalla_de_la_solicitud_muestra_el_formulario_de_importacion(self):
        self.login(self.asis)
        html = self.client.get(reverse("request_detail", args=[self.req.pk])).content.decode()
        self.assertIn('enctype="multipart/form-data"', html)
        self.assertIn("Importar desde un calendario (.ics)", html)
        self.assertIn(self.url(), html)

    def test_lo_importado_alimenta_la_propuesta(self):
        # Ejecutivo importa su calendario libre; la contraparte marca un bloque que coincide.
        self.importar(calendario(evento("UID:a", "DTSTART:20261201T150000Z", "DTEND:20261201T160000Z")))
        Availability.objects.create(request=self.req, party="contraparte", blocks={"1-10": 1, "1-11": 1})
        r = self.client.post(reverse("generate_proposal", args=[self.req.pk]), follow=True)
        self.assertEqual(r.status_code, 200)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "propuesta")


class AyudasDePruebaTests(SimpleTestCase):
    def test_ventana_de_una_semana(self):
        inicio, fin = week_window(LUNES, LIMA)
        self.assertEqual(fin - inicio, timedelta(days=7))
