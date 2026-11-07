from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from meetings.models import SchedulingRule
from scheduling.rules import validate_rule

from .models import Profile, User


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


# ---------------------------------------------------------------- TR-43: onboarding de tres pasos segun el rol

HOURS_FROM = [(h, f"{h:02d}:00") for h in range(0, 24)]
HOURS_TO = [(h, f"{h:02d}:00") for h in range(1, 25)]


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
        outside = (f"Fuera de mi jornada ({start:02d}:00 a {end:02d}:00)" if user.is_executive
                   else "Fuera de la jornada del ejecutivo")
        self.presets = {key: rules for key, _, _, rules in PROTECT_PRESETS}
        self.fields["protect"].choices = [(key, title) for key, title, _, _ in PROTECT_PRESETS] + [(OUTSIDE_WORK, outside)]
        # Para la plantilla: clave, titulo y detalle de cada opcion.
        self.options = [(key, title, detail) for key, title, detail, _ in PROTECT_PRESETS]
        self.options.append((OUTSIDE_WORK, outside, "Protege lo que queda antes y después de la jornada registrada."))

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
            same = SchedulingRule.objects.filter(executive=executive, weekday=weekday, start_hour=start, end_hour=end)
            if same.exists():
                continue  # ya existe (activa o desactivada): no se duplica ni se reactiva
            SchedulingRule.objects.create(executive=executive, created_by=self.user,
                                          weekday=weekday, start_hour=start, end_hour=end)
            created += 1
        return created
