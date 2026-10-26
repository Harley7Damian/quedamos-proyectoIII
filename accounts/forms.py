from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User


class SignupForm(UserCreationForm):
    email = forms.EmailField(label="Correo", max_length=150)
    full_name = forms.CharField(label="Nombre completo", min_length=2, max_length=80)
    role = forms.ChoiceField(label="Mi rol", choices=User.Role.choices, widget=forms.RadioSelect, initial=User.Role.ASISTENTE)

    class Meta:
        model = User
        fields = ("full_name", "email", "role")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("username", None)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con ese correo. Prueba ingresar.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        user.email = self.cleaned_data["email"]
        user.full_name = self.cleaned_data["full_name"].strip()
        user.role = self.cleaned_data["role"]
        if commit:
            user.save()
        return user


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label="Correo", widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}))

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()
