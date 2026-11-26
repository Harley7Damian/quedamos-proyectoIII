"""Crea una reunión aprobada que empieza en unos minutos, para probar los avisos
(Telegram y llamada) sin pasar por la cuadrícula de horas exactas."""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User

from meetings.models import MeetingRequest


class Command(BaseCommand):
    help = "Crea una reunión aprobada de prueba que empieza dentro de N minutos."

    def add_arguments(self, parser):
        parser.add_argument("--ejecutivo", required=True, help="Correo del ejecutivo dueño de la agenda.")
        parser.add_argument("--asistente", help="Correo de quien crea la solicitud (por defecto, el propio ejecutivo).")
        parser.add_argument("--en", type=int, default=35, help="Minutos desde ahora hasta el inicio (por defecto 35).")
        parser.add_argument("--duracion", type=int, default=30, help="Duración en minutos (por defecto 30).")

    def _usuario(self, correo, rol=None):
        usuario = User.objects.filter(username=correo.strip().lower()).first()
        if usuario is None:
            raise CommandError(f"No existe una cuenta con el correo {correo}.")
        if rol and usuario.role != rol:
            raise CommandError(f"La cuenta {correo} no tiene el rol {rol}.")
        return usuario

    def handle(self, *args, **options):
        if options["en"] < 1:
            raise CommandError("--en debe ser al menos 1 minuto.")
        ejecutivo = self._usuario(options["ejecutivo"], User.Role.EJECUTIVO)
        autor = self._usuario(options["asistente"]) if options["asistente"] else ejecutivo
        inicio = timezone.now() + timedelta(minutes=options["en"])
        solicitud = MeetingRequest.objects.create(
            executive=ejecutivo, created_by=autor, title="Reunión de prueba de avisos",
            counterpart_name="Contraparte de prueba", duration_min=options["duracion"],
            status=MeetingRequest.Status.APROBADA, week_start=timezone.localtime(inicio).date(),
            approved_start=inicio, approved_end=inicio + timedelta(minutes=options["duracion"]),
            decided_at=timezone.now(),
        )
        hora = timezone.localtime(inicio).strftime("%H:%M")
        self.stdout.write(f"Reunión de prueba {solicitud.pk} creada. Empieza a las {hora} (hora de Lima).")
