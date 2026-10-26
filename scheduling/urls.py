from django.urls import path

from . import views

urlpatterns = [path("demo/tarjeta/", views.demo_card, name="demo_card")]
