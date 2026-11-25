from django.test import TestCase

from accounts.forms import PhoneForm


class PhoneFormTests(TestCase):
    def test_numero_valido_pasa(self):
        form = PhoneForm(data={"telefono": "+51999999999"})
        self.assertTrue(form.is_valid())

    def test_numero_sin_mas_no_pasa(self):
        form = PhoneForm(data={"telefono": "999999999"})
        self.assertFalse(form.is_valid())

    def test_texto_invalido_no_pasa(self):
        form = PhoneForm(data={"telefono": "no es un numero"})
        self.assertFalse(form.is_valid())

    def test_vacio_es_valido(self):
        form = PhoneForm(data={"telefono": ""})
        self.assertTrue(form.is_valid())
