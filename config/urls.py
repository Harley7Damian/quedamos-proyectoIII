from django.contrib import admin
from django.urls import include, path

from .health import health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("salud/", health, name="health"),
    path("", include("accounts.urls")),
    path("", include("meetings.urls")),
    path("", include("scheduling.urls")),
]
