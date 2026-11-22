"""Comando programado (TR-76/TR-79): revisa las reuniones aprobadas y manda los
recordatorios de Telegram. Usa ventanas tolerantes (no un minuto exacto) para
sobrevivir a reuniones creadas tarde o a retrasos del cron, y aísla errores por
solicitud para que una falla no detenga a las demás."""
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
        # 30 min o menos, pero más de 5 (para no pisar la ventana del de 5 min).
        self._procesar(
            ahora, limite_inferior=5, limite_superior=30,
            campo="recordatorio_30_enviado_en", generar_texto=mensaje_recordatorio_30,
        )
        # 5 min o menos, pero la reunión todavía no empezó.
        self._procesar(
            ahora, limite_inferior=0, limite_superior=5,
            campo="recordatorio_5_enviado_en", generar_texto=mensaje_recordatorio_5,
        )

    def _procesar(self, ahora, limite_inferior, limite_superior, campo, generar_texto):
        desde = ahora + timedelta(minutes=limite_inferior)
        hasta = ahora + timedelta(minutes=limite_superior)
        pendientes = MeetingRequest.objects.filter(
            status=MeetingRequest.Status.APROBADA,
            approved_start__gt=desde,
            approved_start__lte=hasta,
            **{f"{campo}__isnull": True},
        )
        for solicitud in pendientes:
            try:
                texto = generar_texto(solicitud)
                for perfil in self._destinatarios(solicitud):
                    enviar_mensaje_telegram(perfil.telegram_chat_id, texto)
                setattr(solicitud, campo, ahora)
                solicitud.save(update_fields=[campo])
                self.stdout.write(
                    f"Recordatorio ({limite_superior} min) enviado para la solicitud {solicitud.pk}."
                )
            except Exception as exc:
                self.stderr.write(
                    f"No se pudo enviar el recordatorio de la solicitud {solicitud.pk}: {type(exc).__name__}"
                )

    def _destinatarios(self, solicitud):
        usuarios = {solicitud.executive_id, solicitud.created_by_id}
        return Profile.objects.filter(user_id__in=usuarios, telegram_chat_id__isnull=False)
