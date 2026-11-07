from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from scheduling.rules import DAY_NAMES, RuleSpec

from .weeks import monday_of


class AssistantLink(models.Model):
    """Vinculo entre una asistente y un ejecutivo. Una asistente puede atender a varios."""

    assistant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="executive_links")
    executive = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assistant_links")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["assistant", "executive"], name="unique_assistant_executive"),
            models.CheckConstraint(condition=~Q(assistant=models.F("executive")), name="assistant_is_not_executive"),
        ]

    def __str__(self) -> str:
        return f"{self.assistant} -> {self.executive}"


class MeetingRequestQuerySet(models.QuerySet):
    def visible_to(self, user):
        """Regla de visibilidad: solicitudes de mi propio calendario (ejecutivo) o de un ejecutivo al que sigo vinculada (asistente)."""
        linked_execs = AssistantLink.objects.filter(assistant=user).values("executive")
        return self.filter(Q(executive=user) | Q(executive__in=linked_execs))


class MeetingRequest(models.Model):
    class Status(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        PROPUESTA = "propuesta", "Propuesta"
        APROBADA = "aprobada", "Aprobada"
        CANCELADA = "cancelada", "Cancelada"

    DURATIONS = [(m, f"{m} minutos") for m in (15, 30, 45, 60, 90, 120)]

    executive = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="meeting_requests")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_requests")
    title = models.CharField("asunto", max_length=120)
    duration_min = models.PositiveSmallIntegerField("duración", choices=DURATIONS, default=30)
    counterpart_name = models.CharField("contraparte", max_length=80)
    counterpart_email = models.EmailField("correo de la contraparte", max_length=120, blank=True)
    notes = models.TextField("notas", max_length=500, blank=True)
    status = models.CharField("estado", max_length=10, choices=Status.choices, default=Status.PENDIENTE)
    week_start = models.DateField("semana a coordinar (lunes)", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # HU-08: decision del ejecutivo desde el enlace de aprobacion.
    approved_start = models.DateTimeField("inicio aprobado", null=True, blank=True)
    approved_end = models.DateTimeField("fin aprobado", null=True, blank=True)
    decided_at = models.DateTimeField("aprobada el", null=True, blank=True)
    new_options_requested_at = models.DateTimeField("otras opciones pedidas el", null=True, blank=True)

    objects = MeetingRequestQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["executive", "-created_at"])]

    def __str__(self) -> str:
        return self.title

    @property
    def effective_week_start(self):
        """Lunes de la semana a coordinar. Si no se eligio, la semana en que se creo la solicitud."""
        if self.week_start:
            return self.week_start
        return monday_of(timezone.localtime(self.created_at).date())

    @property
    def accepts_availability(self) -> bool:
        return self.status in (self.Status.PENDIENTE, self.Status.PROPUESTA)

    @property
    def is_approved(self) -> bool:
        return self.status == self.Status.APROBADA and self.approved_start is not None

    def approve(self, start, end):
        """Registra la opcion elegida por el ejecutivo. Una solicitud ya aprobada no se modifica."""
        if self.status != self.Status.PROPUESTA:
            return False
        self.status = self.Status.APROBADA
        self.approved_start, self.approved_end = start, end
        self.decided_at = timezone.now()
        self.new_options_requested_at = None
        self.save(update_fields=["status", "approved_start", "approved_end", "decided_at", "new_options_requested_at"])
        return True

    def request_new_options(self):
        """El ejecutivo rechaza todas las opciones: vuelve a pendiente y queda anotado para la asistente."""
        if self.status != self.Status.PROPUESTA:
            return False
        self.status = self.Status.PENDIENTE
        self.new_options_requested_at = timezone.now()
        self.save(update_fields=["status", "new_options_requested_at"])
        return True


class Availability(models.Model):
    """Bloques de una hora en que una de las dos partes puede reunirse, dentro de la semana de la solicitud.

    blocks guarda {"<dia>-<hora>": 1 o 2}: dia 0 es lunes; 1 es disponible y 2 es preferido.
    """

    class Party(models.TextChoices):
        EJECUTIVO = "ejecutivo", "Ejecutivo"
        CONTRAPARTE = "contraparte", "Contraparte"

    request = models.ForeignKey(MeetingRequest, on_delete=models.CASCADE, related_name="availabilities")
    party = models.CharField(max_length=12, choices=Party.choices)
    blocks = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["request", "party"], name="unique_availability_per_party")]

    def __str__(self) -> str:
        return f"{self.request} ({self.party})"


class SchedulingRule(models.Model):
    """Franja protegida de un ejecutivo: las propuestas no pueden caer dentro de ella (HU-07)."""

    WEEKDAYS = [(i, name.capitalize()) for i, name in enumerate(DAY_NAMES)]

    executive = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="scheduling_rules")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_rules")
    weekday = models.PositiveSmallIntegerField("día", choices=WEEKDAYS, null=True, blank=True)
    start_hour = models.PositiveSmallIntegerField("desde")
    end_hour = models.PositiveSmallIntegerField("hasta")
    active = models.BooleanField("activa", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["executive", "weekday", "start_hour"]
        constraints = [
            models.CheckConstraint(
                condition=Q(start_hour__gte=0, start_hour__lte=23, end_hour__gte=1, end_hour__lte=24, start_hour__lt=models.F("end_hour")),
                name="rule_hours_valid",
            ),
        ]

    def spec(self) -> RuleSpec:
        return RuleSpec(weekday=self.weekday, start_hour=self.start_hour, end_hour=self.end_hour)

    @property
    def label(self) -> str:
        return self.spec().label

    def __str__(self) -> str:
        return f"{self.executive}: {self.label}"
