from django.urls import path

from . import views

urlpatterns = [
    path("panel/captura/", views.capturar, name="ia_capturar"),
    path("panel/captura/reglas/", views.confirmar_reglas, name="ia_confirmar_reglas"),
    path("panel/solicitudes/<int:pk>/acuerdos/generar/", views.acuerdos_generar, name="ia_acuerdos_generar"),
    path("panel/solicitudes/<int:pk>/acuerdos/confirmar/", views.acuerdos_confirmar, name="ia_acuerdos_confirmar"),
    path("panel/solicitudes/<int:pk>/seguimiento/", views.seguimiento, name="ia_seguimiento"),
]
