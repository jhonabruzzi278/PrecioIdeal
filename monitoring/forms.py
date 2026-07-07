from django import forms

from monitoring.models import Monitor, UpdateSchedule


class MonitorForm(forms.ModelForm):
    category = forms.CharField(
        label="Categoría Knasta",
        required=True,
        widget=forms.HiddenInput(),
    )

    class Meta:
        model = Monitor
        fields = ["name", "active"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ej: Smartphones",
                    "id": "id_monitor_name",
                }
            ),
            "active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "name": "Nombre",
            "active": "Activo",
        }

    def __init__(self, *args, categories=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.categories_by_value = {}
        for item in categories or []:
            if not item.get("slug"):
                continue
            value = f"{item['category_id']}|{item['slug']}"
            self.categories_by_value[value] = item
        if self.instance.pk and self.instance.category_id:
            self.fields["category"].initial = (
                f"{self.instance.category_id}|{self.instance.category_slug}"
            )

    def clean_category(self):
        value = (self.cleaned_data.get("category") or "").strip()
        if not value or "|" not in value:
            raise forms.ValidationError("Selecciona una categoría de la lista.")
        if value not in self.categories_by_value:
            raise forms.ValidationError("La categoría seleccionada no es válida.")
        item = self.categories_by_value[value]
        category_id, category_slug = value.split("|", 1)
        return {
            "category_id": category_id,
            "category_slug": category_slug,
            "category_name": item.get("long_path") or item.get("category_name", ""),
        }

    def save(self, commit=True):
        category_data = self.cleaned_data["category"]
        self.instance.category_id = category_data["category_id"]
        self.instance.category_slug = category_data["category_slug"]
        self.instance.category_name = category_data["category_name"]
        return super().save(commit=commit)


class UpdateScheduleForm(forms.ModelForm):
    class Meta:
        model = UpdateSchedule
        fields = ["enabled", "interval_hours"]
        widgets = {
            "enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "interval_hours": forms.NumberInput(
                attrs={"class": "form-control", "min": 1, "max": 168}
            ),
        }
        labels = {
            "enabled": "Activar actualización automática",
            "interval_hours": "Intervalo (horas)",
        }
