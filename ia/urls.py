from django.urls import path

from . import tareas, views

urlpatterns = [
    path("panel/captura/", views.capturar, name="ia_capturar"),
    path("panel/captura/reglas/", views.confirmar_reglas, name="ia_confirmar_reglas"),
    path("panel/solicitudes/<int:pk>/acuerdos/generar/", views.acuerdos_generar, name="ia_acuerdos_generar"),
    path("panel/solicitudes/<int:pk>/acuerdos/confirmar/", views.acuerdos_confirmar, name="ia_acuerdos_confirmar"),
    path("panel/solicitudes/<int:pk>/seguimiento/", views.seguimiento, name="ia_seguimiento"),
    path("panel/tareas/", tareas.tablero, name="ia_tareas"),
    path("panel/tareas/exportar.csv", tareas.exportar_csv, name="ia_tareas_csv"),
    path("panel/tareas/<int:pk>/estado/", tareas.cambiar_estado, name="ia_tarea_estado"),
]
