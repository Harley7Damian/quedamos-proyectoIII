import secrets

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q

# Sin caracteres ambiguos (0/O, 1/I) para que el codigo se pueda dictar por telefono.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6


def generate_link_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def normalize_code(raw: str) -> str:
    return "".join(ch for ch in (raw or "").upper() if ch.isalnum())


class User(AbstractUser):
    """Usuario de Quedamos. El correo se guarda tambien como username."""

    class Role(models.TextChoices):
        ASISTENTE = "asistente", "Asistente"
        EJECUTIVO = "ejecutivo", "Ejecutivo"

    full_name = models.CharField("nombre completo", max_length=80)
    role = models.CharField("rol", max_length=10, choices=Role.choices, default=Role.ASISTENTE)
    link_code = models.CharField("código de vinculación", max_length=CODE_LENGTH, unique=True, null=True, blank=True, editable=False)

    @property
    def is_executive(self) -> bool:
        return self.role == self.Role.EJECUTIVO

    @property
    def is_assistant(self) -> bool:
        return self.role == self.Role.ASISTENTE

    def save(self, *args, **kwargs):
        # Solo el ejecutivo tiene codigo; se genera una vez y no cambia.
        if self.is_executive and not self.link_code:
            code = generate_link_code()
            while User.objects.filter(link_code=code).exists():
                code = generate_link_code()
            self.link_code = code
        if not self.is_executive:
            self.link_code = None
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.full_name or self.username


class Profile(models.Model):
    """Respuestas del onboarding (TR-43): área y jornada laboral, y si se completó u omitió."""

    class Area(models.TextChoices):
        DIRECCION = "direccion", "Dirección general"
        FINANZAS = "finanzas", "Finanzas"
        COMERCIAL = "comercial", "Comercial y ventas"
        OPERACIONES = "operaciones", "Operaciones"
        PERSONAS = "personas", "Recursos humanos"
        LEGAL = "legal", "Legal"
        TECNOLOGIA = "tecnologia", "Tecnología"
        OTRA = "otra", "Otra área"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    area = models.CharField("área", max_length=20, choices=Area.choices, blank=True)
    work_start = models.PositiveSmallIntegerField("inicio de la jornada", default=9)
    work_end = models.PositiveSmallIntegerField("fin de la jornada", default=18)
    onboarding_completed_at = models.DateTimeField("onboarding completado", null=True, blank=True)
    onboarding_skipped_at = models.DateTimeField("onboarding omitido", null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "perfil"
        verbose_name_plural = "perfiles"
        constraints = [
            models.CheckConstraint(
                condition=Q(work_start__gte=0, work_start__lte=23, work_end__gte=1, work_end__lte=24, work_start__lt=models.F("work_end")),
                name="profile_work_hours_valid",
            ),
        ]

    @property
    def onboarding_done(self) -> bool:
        return self.onboarding_completed_at is not None or self.onboarding_skipped_at is not None

    def __str__(self) -> str:
        return f"Perfil de {self.user}"
