from django.shortcuts import redirect, render
from django.views.decorators.http import require_safe

from .mock import MOCK_PROPOSAL


def demo_card(request):
    """Maqueta de la tarjeta de aprobacion con datos de ejemplo (sin base de datos)."""
    return render(request, "demo/tarjeta.html", {"proposal": MOCK_PROPOSAL})


@require_safe
def landing(request):
    """Pagina publica de presentacion (TR-44). Quien ya tiene sesion pasa directo al panel."""
    if request.user.is_authenticated:
        return redirect("panel")
    return render(request, "landing.html", {"proposal": MOCK_PROPOSAL})
