"""Prueba de humo de la IA con la clave real: python manage.py probar_ia (consume 1 llamada del cupo)."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ia.esquemas import Entero, Objeto, Opcion, Texto
from ia.gemini import IaError, pedir_json_detallado

ESQUEMA = Objeto(
    {
        "asunto": Texto(120),
        "duracion_min": Opcion((30, 45, 60, 90)),
        "contraparte": Texto(80, nullable=True),
        "semana": Opcion(("esta", "proxima"), nullable=True),
        "dia": Entero(0, 6, nullable=True),
    }
)
INSTRUCCION = (
    'Devuelve JSON con las claves "asunto" (texto), "duracion_min" (30, 45, 60 o 90), "contraparte" (texto o null), '
    '"semana" ("esta", "proxima" o null) y "dia" (0 a 6 con lunes igual a 0, o null).'
)
TEXTO = "Reunión con el proveedor de Alicorp de una hora la próxima semana para revisar el contrato."


class Command(BaseCommand):
    help = "Hace una llamada real a Gemini con un texto ficticio y muestra el modelo que respondio."

    def handle(self, *args, **options):
        if not settings.GEMINI_API_KEY:
            raise CommandError("Falta la variable de entorno GEMINI_API_KEY.")
        try:
            datos, modelo = pedir_json_detallado(None, INSTRUCCION, TEXTO, ESQUEMA)
        except IaError as error:
            raise CommandError(f"La IA no respondió bien: {error.mensaje_usuario}") from None
        self.stdout.write(f"Modelo que respondió: {modelo}")
        self.stdout.write(f"Respuesta validada: {datos}")
        self.stdout.write(self.style.SUCCESS("La IA funciona."))
