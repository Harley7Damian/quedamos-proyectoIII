from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import EmailAuthenticationForm

urlpatterns = [
    path("acceso/", auth_views.LoginView.as_view(authentication_form=EmailAuthenticationForm, redirect_authenticated_user=True), name="login"),
    path("registro/", views.signup, name="signup"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
]
