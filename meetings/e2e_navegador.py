import sys

from playwright.sync_api import sync_playwright

if sys.platform == "win32":
    # TR-38: en Windows, StaticLiveServerTestCase falla con un error de
    # url2pathname cuando una URL contiene "|" (como nuestros enlaces
    # firmados). En Linux, donde corre el pipeline de CI, este error no
    # existe. Este parche solo se aplica en Windows, para poder probar
    # el recorrido completo en la máquina local.
    import django.test.testcases as _django_testcases
    from urllib.parse import unquote as _unquote
    _django_testcases.url2pathname = lambda path: _unquote(path)

from django.contrib.staticfiles.testing import StaticLiveServerTestCase


class RecorridoCompletoTests(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        super().tearDownClass()

    def _omitir_onboarding(self, page):
        page.click('text=Omitir por ahora')
        page.wait_for_url("**/panel/")

    def _marcar_un_dia_completo_disponible(self, page):
        """Marca como 'Disponible' todas las horas de un mismo dia (la segunda columna de la tabla)
        para asegurar un bloque continuo suficiente para cualquier duracion."""
        celdas = page.locator("table.avail tbody tr td:nth-child(2) button")
        for i in range(celdas.count()):
            celdas.nth(i).click()

    def _captura(self, page, nombre):
        try:
            page.screenshot(path=f"capturas/{nombre}")
        except Exception as error:
            print(f"Aviso: no se pudo guardar la captura {nombre}: {error}")

    def test_recorrido_de_extremo_a_extremo(self):
        contexto_ejecutivo = self.browser.new_context()
        contexto_asistente = self.browser.new_context()
        contexto_contraparte = self.browser.new_context()
        ejecutivo = contexto_ejecutivo.new_page()
        asistente = contexto_asistente.new_page()
        contraparte = contexto_contraparte.new_page()

        # 1. El ejecutivo crea su cuenta
        ejecutivo.goto(f"{self.live_server_url}/registro/")
        ejecutivo.fill('input[name="full_name"]', "Rocio Damian Gavino")
        ejecutivo.fill('input[name="email"]', "rocio.ejecutiva@example.com")
        ejecutivo.get_by_label("Ejecutivo").check()
        ejecutivo.fill('input[name="password1"]', "ClaveSegura123")
        ejecutivo.fill('input[name="password2"]', "ClaveSegura123")
        self._captura(ejecutivo, "01-registro-ejecutivo.png")
        ejecutivo.click('button[type="submit"]')
        ejecutivo.wait_for_url("**/bienvenida/**")
        self._omitir_onboarding(ejecutivo)
        codigo = ejecutivo.locator("#mycode").inner_text()
        self._captura(ejecutivo, "02-codigo-vinculacion.png")

        # 2. La asistente crea su cuenta
        asistente.goto(f"{self.live_server_url}/registro/")
        asistente.fill('input[name="full_name"]', "Ana Torres")
        asistente.fill('input[name="email"]', "ana.asistente@example.com")
        asistente.get_by_label("Asistente").check()
        asistente.fill('input[name="password1"]', "ClaveSegura123")
        asistente.fill('input[name="password2"]', "ClaveSegura123")
        asistente.click('button[type="submit"]')
        asistente.wait_for_url("**/bienvenida/**")
        self._omitir_onboarding(asistente)

        # 3. La asistente se vincula con el código del ejecutivo
        asistente.fill('#codigo-vinculo', codigo)
        asistente.get_by_role("button", name="Vincular", exact=True).click()
        self._captura(asistente, "03-vinculacion.png")

        # 4. La asistente crea una solicitud de reunión
        asistente.click('text=+ Nueva solicitud de reunión')
        asistente.select_option('select[name="executive"]', label="Rocio Damian Gavino")
        asistente.fill('input[name="title"]', "Revisión trimestral de ventas")
        asistente.fill('input[name="counterpart_name"]', "Pedro Gómez")
        asistente.fill('input[name="counterpart_email"]', "pedro.gomez@empresa.com")
        asistente.select_option('select[name="duration_min"]', "45")
        self._captura(asistente, "04-nueva-solicitud.png")
        asistente.click('form[action*="nueva"] button[type="submit"]')
        asistente.wait_for_selector("text=Revisión trimestral de ventas")
        ejecutivo.reload()
        ejecutivo.wait_for_selector("text=Revisión trimestral de ventas", timeout=8000)
        self._captura(ejecutivo, "05-aparece-en-panel-ejecutivo.png")

        # 5. La asistente entra al detalle y genera el enlace para la contraparte
        asistente.click('text=Ver detalle y coordinar')
        asistente.get_by_role("button", name="Generar enlace para la contraparte").click()
        enlace_contraparte = asistente.locator("#enlace").input_value()

        # 6. La contraparte marca su disponibilidad desde el enlace, sin cuenta
        contraparte.goto(enlace_contraparte)
        self._marcar_un_dia_completo_disponible(contraparte)
        contraparte.get_by_role("button", name="Enviar mi disponibilidad").click()
        contraparte.wait_for_load_state("load")
        self._captura(contraparte, "06-disponibilidad-contraparte.png")

        # 7. La asistente marca la disponibilidad del ejecutivo en la misma solicitud
        self._marcar_un_dia_completo_disponible(asistente)
        asistente.get_by_role("button", name="Guardar disponibilidad del ejecutivo").click()
        asistente.wait_for_load_state("load")
        self._captura(asistente, "07-disponibilidad-ejecutivo.png")

        # 8. La asistente genera la propuesta de tres horarios
        asistente.get_by_role("button", name="Generar propuesta de tres horarios").click()
        asistente.wait_for_selector("text=Opción 1")
        self._captura(asistente, "08-propuesta-generada.png")

        # 9. La asistente genera el enlace de aprobación para el ejecutivo
        asistente.get_by_role("button", name="Generar enlace de aprobación para el ejecutivo").click()
        enlace_aprobacion = asistente.locator("#enlace-aprobacion").input_value()

        # 10. El ejecutivo aprueba una opción con un toque, desde el enlace, sin iniciar sesión de nuevo
        ejecutivo.goto(enlace_aprobacion)
        ejecutivo.get_by_role("button", name="Aprobar esta opción").first.click()
        ejecutivo.wait_for_selector("text=Reunión confirmada")
        self._captura(ejecutivo, "09-reunion-confirmada.png")

        contexto_ejecutivo.close()
        contexto_asistente.close()
        contexto_contraparte.close()
