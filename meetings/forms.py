from datetime import date

from django import forms
from django.utils import timezone

from accounts.models import User, normalize_code

from scheduling.rules import validate_rule

from .models import MeetingRequest, SchedulingRule
from .weeks import default_week_start, week_choices


class LinkForm(forms.Form):
    code = forms.CharField(label="Código del ejecutivo", max_length=12)

    def clean_code(self):
        return normalize_code(self.cleaned_data["code"])


class MeetingRequestForm(forms.ModelForm):
    class Meta:
        model = MeetingRequest
        fields = ["executive", "title", "counterpart_name", "counterpart_email", "duration_min", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    week = forms.ChoiceField(label="Semana a coordinar", required=False)

    def __init__(self, *args, user: User, executives, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        # Solo se puede elegir entre los ejecutivos vinculados: la validacion no depende de la pantalla.
        self.fields["executive"].queryset = executives
        self.fields["executive"].label = "Ejecutivo"
        self.fields["executive"].empty_label = None
        self.fields["title"].min_length = 3
        self.fields["counterpart_name"].min_length = 2
        today = timezone.localdate()
        self.fields["week"].choices = week_choices(today)
        self.fields["week"].initial = default_week_start(today).isoformat()

    def clean_title(self):
        value = self.cleaned_data["title"].strip()
        if len(value) < 3:
            raise forms.ValidationError("El asunto debe tener al menos 3 caracteres.")
        return value

    def clean_counterpart_name(self):
        value = self.cleaned_data["counterpart_name"].strip()
        if len(value) < 2:
            raise forms.ValidationError("Escribe el nombre de la contraparte.")
        return value

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.created_by = self.user  # lo define el servidor, nunca el formulario
        chosen = self.cleaned_data.get("week") or default_week_start(timezone.localdate()).isoformat()
        obj.week_start = date.fromisoformat(chosen)
        if commit:
            obj.save()
        return obj


class SchedulingRuleForm(forms.ModelForm):
    """Alta y edición de una franja protegida. El ejecutivo solo se elige al crear, entre los vinculados."""

    weekday = forms.TypedChoiceField(
        label="Día", required=False, coerce=int, empty_value=None,
        choices=[("", "Todos los días")] + SchedulingRule.WEEKDAYS,
    )
    start_hour = forms.TypedChoiceField(label="Desde", coerce=int, choices=[(h, f"{h:02d}:00") for h in range(0, 24)])
    end_hour = forms.TypedChoiceField(label="Hasta", coerce=int, choices=[(h, f"{h:02d}:00") for h in range(1, 25)])

    class Meta:
        model = SchedulingRule
        fields = ["executive", "weekday", "start_hour", "end_hour"]

    def __init__(self, *args, user: User, executives, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["end_hour"].initial = 10  # el caso más común: "nada antes de las 10:00"
        if self.instance.pk:
            del self.fields["executive"]
        else:
            self.fields["executive"].queryset = executives
            self.fields["executive"].label = "Ejecutivo"
            self.fields["executive"].empty_label = None

    def clean(self):
        data = super().clean()
        if {"start_hour", "end_hour"} <= data.keys():
            error = validate_rule(data.get("weekday"), data["start_hour"], data["end_hour"])
            if error:
                raise forms.ValidationError(error)
        return data

    def save(self, commit=True):
        obj = super().save(commit=False)
        if not obj.pk:
            obj.created_by = self.user  # lo define el servidor, nunca el formulario
        if commit:
            obj.save()
        return obj
