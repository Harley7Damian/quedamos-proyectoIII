"""Comando programado (TR-76): revisa las reuniones aprobadas y manda los recordatorios de Telegram."""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Profile
from accounts.recordatorios import mensaje_recordatorio_5, mensaje_recordatorio_30
from accounts.telegram import enviar_mensaje_telegram

from meetings.models import MeetingRequest


class Command(BaseCommand):
    help = "Envia los recordatorios de Telegram 30 y 5 minutos antes de cada reunion aprobada."

    def handle(self, *args, **options):
        ahora = timezone.now()
        self._procesar(ahora, minutos=30, campo="recordatorio_30_enviado_en", generar_texto=mensaje_recordatorio_30)
        self._procesar(ahora, minutos=5, campo="recordatorio_5_enviado_en", generar_texto=mensaje_recordatorio_5)

    def _procesar(self, ahora, minutos, campo, generar_texto):
        desde = ahora + timedelta(minutes=minutos)
        hasta = desde + timedelta(minutes=1)
        pendientes = MeetingRequest.objects.filter(
            status=MeetingRequest.Status.APROBADA,
            approved_start__gte=desde,
            approved_start__lt=hasta,
            **{f"{campo}__isnull": True},
        )
        for solicitud in pendientes:
            texto = generar_texto(solicitud)
            for perfil in self._destinatarios(solicitud):
                enviar_mensaje_telegram(perfil.telegram_chat_id, texto)
            setattr(solicitud, campo, ahora)
            solicitud.save(update_fields=[campo])
            self.stdout.write(f"Recordatorio de {minutos} min enviado para la solicitud {solicitud.pk}.")

    def _destinatarios(self, solicitud):
        usuarios = {solicitud.executive_id, solicitud.created_by_id}
        return Profile.objects.filter(user_id__in=usuarios, telegram_chat_id__isnull=False)
