from datetime import date

from django import forms
from django.utils import timezone

from accounts.models import User, normalize_code

from scheduling.matching import hour_choices
from scheduling.rules import validate_rule

from .models import MeetingRequest, SchedulingRule
from .weeks import default_week_start, monday_of


class LinkForm(forms.Form):
    code = forms.CharField(label="Código del ejecutivo", max_length=12)

    def clean_code(self):
        return normalize_code(self.cleaned_data["code"])


class MeetingRequestForm(forms.ModelForm):
    class Meta:
        model = MeetingRequest
        fields = ["executive", "title", "counterpart_name", "counterpart_email", "duration_min", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    week = forms.DateField(
        label="Semana a coordinar (elige cualquier día de esa semana)",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )

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
        self.fields["week"].initial = default_week_start(today)
        self.fields["week"].widget.attrs["min"] = monday_of(today).isoformat()

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

    def clean_week(self):
        value = self.cleaned_data.get("week")
        if not value:
            return value
        monday = monday_of(value)
        if monday < monday_of(timezone.localdate()):
            raise forms.ValidationError("Elige un día de esta semana o de una semana futura.")
        return monday

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.created_by = self.user  # lo define el servidor, nunca el formulario
        obj.week_start = self.cleaned_data.get("week") or default_week_start(timezone.localdate())
        if commit:
            obj.save()
        return obj

class SchedulingRuleForm(forms.ModelForm):
    """Alta y edición de una franja protegida. El ejecutivo solo se elige al crear, entre los vinculados."""

    weekday = forms.TypedChoiceField(
        label="Día", required=False, coerce=int, empty_value=None,
        choices=[("", "Todos los días")] + SchedulingRule.WEEKDAYS,
    )
    start_hour = forms.TypedChoiceField(label="Desde", coerce=int, choices=hour_choices(0, 23))
    end_hour = forms.TypedChoiceField(label="Hasta", coerce=int, choices=hour_choices(1, 24))

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
