"""Comando programado (TR-76/TR-79/TR-85): revisa las reuniones aprobadas y manda
los recordatorios de Telegram. Usa ventanas tolerantes (no un minuto exacto) para
sobrevivir a reuniones creadas tarde o a retrasos del cron, y aísla errores por
solicitud para que una falla no detenga a las demás. El recordatorio de 5 minutos
además escala a una llamada real si la persona no confirmó con /visto."""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.llamadas import hacer_llamada_recordatorio
from accounts.models import Profile
from accounts.recordatorios import mensaje_recordatorio_5, mensaje_recordatorio_30
from accounts.telegram import enviar_mensaje_telegram

from meetings.models import MeetingRequest


class Command(BaseCommand):
    help = "Envia los recordatorios de Telegram 30 y 5 minutos antes de cada reunion aprobada, con llamada de escalamiento."

    def handle(self, *args, **options):
        ahora = timezone.now()
        self._procesar_30(ahora)
        self._procesar_5(ahora)

    def _procesar_30(self, ahora):
        """Solo Telegram, como hasta ahora."""
        desde = ahora + timedelta(minutes=5)
        hasta = ahora + timedelta(minutes=30)
        pendientes = MeetingRequest.objects.filter(
            status=MeetingRequest.Status.APROBADA,
            approved_start__gt=desde,
            approved_start__lte=hasta,
            recordatorio_30_enviado_en__isnull=True,
        ).order_by("approved_start", "pk")
        for solicitud in pendientes:
            try:
                texto = mensaje_recordatorio_30(solicitud)
                for perfil in self._perfiles(solicitud):
                    if perfil.telegram_chat_id:
                        enviar_mensaje_telegram(perfil.telegram_chat_id, texto)
                solicitud.recordatorio_30_enviado_en = ahora
                solicitud.save(update_fields=["recordatorio_30_enviado_en"])
                self.stdout.write(f"Recordatorio (30 min) enviado para la solicitud {solicitud.pk}.")
            except Exception as exc:
                self.stderr.write(f"No se pudo enviar el recordatorio de la solicitud {solicitud.pk}: {type(exc).__name__}")

    def _procesar_5(self, ahora):
        """Telegram y, si todavia no confirmaron con /visto, llamada real (TR-85)."""
        desde = ahora
        hasta = ahora + timedelta(minutes=5)
        pendientes = MeetingRequest.objects.filter(
            status=MeetingRequest.Status.APROBADA,
            approved_start__gt=desde,
            approved_start__lte=hasta,
            recordatorio_5_enviado_en__isnull=True,
        ).order_by("approved_start", "pk")
        for solicitud in pendientes:
            try:
                texto = mensaje_recordatorio_5(solicitud)
                perfiles = list(self._perfiles(solicitud))
                for perfil in perfiles:
                    if perfil.telegram_chat_id:
                        enviar_mensaje_telegram(perfil.telegram_chat_id, texto)
                if solicitud.confirmado_en is None:
                    for perfil in perfiles:
                        if perfil.telefono:
                            hacer_llamada_recordatorio(perfil.telefono, texto)
                solicitud.recordatorio_5_enviado_en = ahora
                solicitud.save(update_fields=["recordatorio_5_enviado_en"])
                self.stdout.write(f"Recordatorio (5 min) enviado para la solicitud {solicitud.pk}.")
            except Exception as exc:
                self.stderr.write(f"No se pudo enviar el recordatorio de la solicitud {solicitud.pk}: {type(exc).__name__}")

    def _perfiles(self, solicitud):
        usuarios = {solicitud.executive_id, solicitud.created_by_id}
        return Profile.objects.filter(user_id__in=usuarios)
