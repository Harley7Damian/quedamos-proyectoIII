from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import EmailAuthenticationForm

urlpatterns = [
    path("acceso/", auth_views.LoginView.as_view(authentication_form=EmailAuthenticationForm, redirect_authenticated_user=True), name="login"),
    path("registro/", views.signup, name="signup"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("bienvenida/", views.onboarding, name="onboarding"),
    path("bienvenida/<int:step>/", views.onboarding, name="onboarding_step"),
    path("bienvenida/omitir/", views.skip_onboarding, name="skip_onboarding"),
    path("telegram/generar-codigo/", views.telegram_generar_codigo, name="telegram_generar_codigo"),
    path("telegram/desvincular/", views.telegram_desvincular, name="telegram_desvincular"),
    path("telegram/webhook/", views.telegram_webhook, name="telegram_webhook"),
    path("tareas/enviar-recordatorios/", views.ejecutar_recordatorios, name="ejecutar_recordatorios"),
]
