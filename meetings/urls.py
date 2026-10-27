from django.urls import path

from . import views

urlpatterns = [
    path("panel/", views.panel, name="panel"),
    path("panel/solicitudes/", views.request_list, name="request_list"),
    path("panel/vincular/", views.link_executive, name="link_executive"),
    path("panel/vinculo/<int:pk>/eliminar/", views.unlink, name="unlink"),
    path("panel/solicitudes/nueva/", views.create_request, name="create_request"),
    path("panel/solicitudes/<int:pk>/", views.request_detail, name="request_detail"),
    path("panel/solicitudes/<int:pk>/enlace/", views.create_counterpart_link, name="create_counterpart_link"),
    path("c/<str:token>/", views.public_availability, name="public_availability"),
]
