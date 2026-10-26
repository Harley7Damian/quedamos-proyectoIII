import secrets

from django.contrib.auth.models import AbstractUser
from django.db import models

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
