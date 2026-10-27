from datetime import date

from django import forms
from django.utils import timezone

from accounts.models import User, normalize_code

from .models import MeetingRequest
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
