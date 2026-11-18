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


class AcuerdosReunion(models.Model):
    """Notas, resumen y seguimiento propuesto de una reunion aprobada (HU-18). Una sola vez por solicitud.

    Quien ve la solicitud ve estos datos: la visibilidad se decide siempre desde MeetingRequest.visible_to.
    """

    request = models.OneToOneField("meetings.MeetingRequest", on_delete=models.CASCADE, related_name="acuerdos")
    notas = models.TextField("notas")
    resumen = models.TextField("resumen")
    seguimiento_asunto = models.CharField("asunto del seguimiento", max_length=120, blank=True)
    seguimiento_duracion = models.PositiveSmallIntegerField("duración del seguimiento", null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Acuerdos de la solicitud {self.request_id}"

    @property
    def tiene_seguimiento(self) -> bool:
        return bool(self.seguimiento_asunto)


class TareaReunion(models.Model):
    """Tarea que salio de una reunion. El responsable es texto libre: no tiene que ser usuario de Quedamos."""

    acuerdos = models.ForeignKey(AcuerdosReunion, on_delete=models.CASCADE, related_name="tareas")
    descripcion = models.CharField("descripción", max_length=200)
    responsable = models.CharField("responsable", max_length=80, blank=True)
    fecha_limite = models.DateField("fecha límite", null=True, blank=True)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["orden", "id"]

    def __str__(self):
        return self.descripcion
