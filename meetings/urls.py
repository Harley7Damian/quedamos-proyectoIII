from django.urls import path

from . import views

urlpatterns = [
    path("panel/", views.panel, name="panel"),
    path("panel/solicitudes/", views.request_list, name="request_list"),
    path("panel/vincular/", views.link_executive, name="link_executive"),
    path("panel/vinculo/<int:pk>/eliminar/", views.unlink, name="unlink"),
    path("panel/solicitudes/nueva/", views.create_request, name="create_request"),
]
