import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from meetings.models import SchedulingRule
from scheduling.matching import format_span, hour_choices
from scheduling.rules import validate_rule

from .correo import validar_correo
from .models import Profile, User
from .recordatorios import ANTELACIONES, normalizar_antelaciones

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
        self.fields["password1"].widget.attrs["aria-describedby"] = "requisitos-clave"

    def clean_email(self):
        email = validar_correo(self.cleaned_data["email"])
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


# ---------------------------------------------------------------- TR-43: onboarding de tres pasos segun el rol

HOURS_FROM = hour_choices(0, 23)
HOURS_TO = hour_choices(1, 24)


class AreaForm(forms.Form):
    """Paso 1: area de trabajo. El rol ya se eligio en el registro y aqui no se cambia."""

    area = forms.ChoiceField(label="Mi área", choices=Profile.Area.choices, widget=forms.RadioSelect,
                             error_messages={"required": "Elige el área en la que trabajas."})


class WorkHoursForm(forms.ModelForm):
    """Paso 2 del ejecutivo: jornada laboral (las horas se muestran en hora de Lima)."""

    work_start = forms.TypedChoiceField(label="Inicio de la jornada", coerce=int, choices=HOURS_FROM)
    work_end = forms.TypedChoiceField(label="Fin de la jornada", coerce=int, choices=HOURS_TO)

    class Meta:
        model = Profile
        fields = ["work_start", "work_end"]

    def clean(self):
        data = super().clean()
        if {"work_start", "work_end"} <= data.keys() and data["work_start"] >= data["work_end"]:
            raise forms.ValidationError("La jornada debe terminar después de empezar.")
        return data

def normalizar_telefono(crudo: str) -> str:
    """Devuelve el número en formato internacional (+51999999999) o lanza ValueError.

    Acepta espacios, guiones, puntos y paréntesis, pero exige el código del país (+51...)."""
    texto = (crudo or "").strip()
    if not texto:
        return ""
    compacto = re.sub(r"[ \-().]", "", texto)
    if not re.fullmatch(r"\+?\d+", compacto):
        raise ValueError("Escribe solo números, espacios o guiones.")
    digitos = compacto.lstrip("+")
    if not compacto.startswith("+"):
        raise ValueError("Escribe el número con el código del país, por ejemplo +51 999 999 999.")
    if not (8 <= len(digitos) <= 15) or digitos.startswith("0"):
        raise ValueError("El número no parece válido. Usa el formato +51 999 999 999.")
    return "+" + digitos


class PhoneForm(forms.ModelForm):
    """Teléfono para la llamada de escalamiento de recordatorios (TR-85)."""
    class Meta:
        model = Profile
        fields = ["telefono"]
        labels = {"telefono": "Teléfono para llamadas"}
        widgets = {"telefono": forms.TextInput(attrs={"placeholder": "+51 999 999 999", "autocomplete": "tel", "inputmode": "tel"})}

    def clean_telefono(self):
        try:
            return normalizar_telefono(self.cleaned_data.get("telefono", ""))
        except ValueError as exc:
            raise forms.ValidationError(str(exc))


class PerfilDatosForm(forms.Form):
    """Datos que la persona puede cambiar de su cuenta. El correo y el rol no se editan aquí."""

    full_name = forms.CharField(label="Nombre completo", min_length=2, max_length=80)
    area = forms.ChoiceField(label="Área", choices=[("", "Sin indicar")] + list(Profile.Area.choices), required=False)

    def clean_full_name(self):
        return " ".join(self.cleaned_data["full_name"].split())


class AvisosForm(forms.Form):
    """Cuánto antes de cada reunión quiere recibir los avisos (de 2 días a 5 minutos)."""

    MAXIMO = 4

    avisos = forms.MultipleChoiceField(
        label="Avisos de reunión", choices=[(str(m), texto) for m, texto in ANTELACIONES],
        widget=forms.CheckboxSelectMultiple, error_messages={"required": "Elige al menos un aviso."},
    )

    def clean_avisos(self):
        elegidos = normalizar_antelaciones(self.cleaned_data["avisos"])
        if len(elegidos) > self.MAXIMO:
            raise forms.ValidationError(f"Elige como máximo {self.MAXIMO} avisos para no recibir demasiados mensajes.")
        return elegidos


# Horarios a proteger que se ofrecen en el paso 3: (clave, titulo, detalle, reglas como (dia, desde, hasta)).
PROTECT_PRESETS = [
    ("antes_10", "Nada antes de las 10:00", "Las primeras horas quedan para el trabajo interno.", [(None, 0, 10)]),
    ("refrigerio", "Refrigerio de 13:00 a 14:00", "Ninguna propuesta cae en la hora del refrigerio.", [(None, 13, 14)]),
    ("desde_18", "Nada desde las 18:00", "No se proponen reuniones al final del día.", [(None, 18, 24)]),
    ("viernes_tarde", "Viernes por la tarde libre", "Desde las 14:00 del viernes no hay reuniones.", [(4, 14, 24)]),
]
OUTSIDE_WORK = "fuera_jornada"


def outside_work_rules(start: int, end: int):
    """Reglas que cubren lo que queda fuera de la jornada laboral."""
    rules = []
    if start > 0:
        rules.append((None, 0, start))
    if end < 24:
        rules.append((None, end, 24))
    return rules


def work_hours_of(executive: User):
    profile = Profile.objects.filter(user=executive).first()
    return (profile.work_start, profile.work_end) if profile else (9, 18)


class ProtectHoursForm(forms.Form):
    """Paso 3: crea reglas reales (SchedulingRule) para el ejecutivo."""

    executive = forms.ModelChoiceField(label="Ejecutivo", queryset=User.objects.none(), empty_label=None)
    protect = forms.MultipleChoiceField(label="Horarios a proteger", required=False, widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, user: User, executives, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["executive"].queryset = executives
        if user.is_executive:
            self.fields["executive"].initial = user.pk
            self.fields["executive"].widget = forms.HiddenInput()
        start, end = work_hours_of(user) if user.is_executive else (None, None)
        outside = (f"Fuera de mi jornada ({format_span(start, end)})" if user.is_executive
                   else "Fuera de la jornada del ejecutivo")
        self.presets = {key: rules for key, _, _, rules in PROTECT_PRESETS}
        self.fields["protect"].choices = [(OUTSIDE_WORK, outside)] + [(key, title) for key, title, _, _ in PROTECT_PRESETS]
        self.fields["protect"].initial = [OUTSIDE_WORK]
        # Para la plantilla: clave, titulo y detalle de cada opcion.
        self.options = [(OUTSIDE_WORK, outside, "Protege lo que queda antes y después de la jornada registrada.")]
        self.options += [(key, title, detail) for key, title, detail, _ in PROTECT_PRESETS]

    def rules_to_create(self):
        executive = self.cleaned_data["executive"]
        wanted = []
        for key in self.cleaned_data["protect"]:
            wanted += outside_work_rules(*work_hours_of(executive)) if key == OUTSIDE_WORK else self.presets[key]
        return executive, list(dict.fromkeys(wanted))  # sin repetidos, en el mismo orden

    def save(self) -> int:
        """Crea las reglas que aun no existen y devuelve cuantas se crearon."""
        executive, wanted = self.rules_to_create()
        created = 0
        for weekday, start, end in wanted:
            if validate_rule(weekday, start, end):
                continue
            same = SchedulingRule.objects.filter(executive=executive, weekday=weekday, start_hour=start, end_hour=end,
                                                 start_minute=0, end_minute=0)
            if same.exists():
                continue  # ya existe (activa o desactivada): no se duplica ni se reactiva
            SchedulingRule.objects.create(executive=executive, created_by=self.user,
                                          weekday=weekday, start_hour=start, end_hour=end)
            created += 1
        return created
