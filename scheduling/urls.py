from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("demo/tarjeta/", views.demo_card, name="demo_card"),
]
