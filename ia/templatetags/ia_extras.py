from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def ia_activa() -> bool:
    """La captura inteligente solo se muestra si hay una clave de Gemini configurada."""
    return bool(settings.GEMINI_API_KEY)
