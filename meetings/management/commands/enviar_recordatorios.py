"""Comando programado (TR-76/TR-79/TR-85): revisa las reuniones aprobadas y manda los
avisos de Telegram según la antelación que eligió cada persona (por defecto 30 y 5
minutos antes, y hasta 2 días antes). Usa momentos tolerantes (no un minuto exacto)
para sobrevivir a reuniones creadas tarde o a retrasos del cron, y aísla errores por
persona para que una falla no detenga a las demás.

Si varios avisos de una misma persona ya están vencidos a la vez (por ejemplo, la
reunión se aprobó 20 minutos antes y tenía avisos de 1 día, 1 hora y 5 minutos), se
envía solo el más cercano y los otros se marcan como omitidos. El último aviso de
la persona, si es de 15 minutos o menos, escala a una llamada real cuando nadie
confirmó con /visto."""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.llamadas import hacer_llamada_recordatorio
from accounts.models import Profile
from accounts.recordatorios import ANTELACION_MAXIMA, ANTELACION_MAXIMA_LLAMADA, mensaje_aviso, texto_llamada_recordatorio
from accounts.telegram import enviar_mensaje_telegram

from meetings.models import AvisoEnviado, MeetingRequest


class Command(BaseCommand):
    help = "Envía los avisos de Telegram de cada reunión aprobada según la antelación de cada persona, con llamada de escalamiento."

    def handle(self, *args, **options):
        ahora = timezone.now()
        solicitudes = MeetingRequest.objects.filter(
            status=MeetingRequest.Status.APROBADA,
            approved_start__gt=ahora,
            approved_start__lte=ahora + timedelta(minutes=ANTELACION_MAXIMA),
        ).order_by("approved_start", "pk")
        for solicitud in solicitudes:
            for perfil in self._perfiles(solicitud):
                try:
                    self._avisar(solicitud, perfil, ahora)
                except Exception as exc:
                    self.stderr.write(
                        f"No se pudo enviar el aviso de la solicitud {solicitud.pk}: {type(exc).__name__}"
                    )

    def _perfiles(self, solicitud):
        usuarios = {solicitud.executive_id, solicitud.created_by_id}
        return Profile.objects.filter(user_id__in=usuarios).select_related("user")

    def _avisar(self, solicitud, perfil, ahora):
        antelaciones = perfil.avisos_efectivos
        vencidos = [m for m in antelaciones if solicitud.approved_start - timedelta(minutes=m) <= ahora]
        ya_atendidos = set(
            AvisoEnviado.objects.filter(solicitud=solicitud, usuario=perfil.user).values_list("minutos", flat=True)
        )
        pendientes = [m for m in vencidos if m not in ya_atendidos]
        if not pendientes:
            return
        minutos = min(pendientes)  # el más cercano; los demás llegaron tarde y se omiten
        if not perfil.telegram_chat_id and not self._debe_llamar(solicitud, perfil, minutos, antelaciones):
            return  # sin canal: no se marca, para que lo reciba si vincula Telegram dentro de la ventana
        if perfil.telegram_chat_id:
            enviar_mensaje_telegram(perfil.telegram_chat_id, mensaje_aviso(solicitud, minutos))
        if self._debe_llamar(solicitud, perfil, minutos, antelaciones):
            hacer_llamada_recordatorio(perfil.telefono, texto_llamada_recordatorio(solicitud, minutos))
        for m in pendientes:
            AvisoEnviado.objects.get_or_create(
                solicitud=solicitud, usuario=perfil.user, minutos=m,
                defaults={"enviado_en": ahora, "omitido": m != minutos},
            )
        self.stdout.write(f"Aviso ({minutos} min) enviado para la solicitud {solicitud.pk} a {perfil.user_id}.")

    def _debe_llamar(self, solicitud, perfil, minutos, antelaciones):
        return bool(
            perfil.telefono
            and solicitud.confirmado_en is None
            and minutos == min(antelaciones)
            and minutos <= ANTELACION_MAXIMA_LLAMADA
        )
