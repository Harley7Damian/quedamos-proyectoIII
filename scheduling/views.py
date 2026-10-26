from django.shortcuts import render

from .mock import MOCK_PROPOSAL


def demo_card(request):
    """Maqueta de la tarjeta de aprobacion con datos de ejemplo (sin base de datos)."""
    return render(request, "demo/tarjeta.html", {"proposal": MOCK_PROPOSAL})
