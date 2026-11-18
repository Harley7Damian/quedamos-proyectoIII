from django.conf import settings
from django.db import models


class UsoIA(models.Model):
    """Llamadas a la IA que hizo un usuario en un dia (TR-80). Sirve para el tope diario por usuario.

    El cupo gratuito de Gemini es del proyecto completo y se comparte entre todas las personas; este tope evita que
    una sola lo agote. Solo cuenta llamadas: nunca guarda el texto enviado ni la respuesta.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ia_usage")
    date = models.DateField("día")
    calls = models.PositiveIntegerField("llamadas", default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "date"], name="uso_ia_unico_por_usuario_y_dia")]

    def __str__(self):
        return f"{self.user_id} {self.date}: {self.calls}"
