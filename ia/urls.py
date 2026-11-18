from django.urls import path

from . import views

urlpatterns = [
    path("panel/captura/", views.capturar, name="ia_capturar"),
    path("panel/captura/reglas/", views.confirmar_reglas, name="ia_confirmar_reglas"),
]
