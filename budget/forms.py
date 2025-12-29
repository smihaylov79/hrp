from django import forms
from .models import Budget, BudgetItem
import datetime


class BudgetForm(forms.ModelForm):
    current_year = datetime.date.today().year
    YEARS = [(y, y) for y in range(current_year - 1, current_year + 6)]

    year = forms.ChoiceField(
        label="Година",
        choices=YEARS,
        widget=forms.Select(attrs={"class": "form-select"})
    )

    class Meta:
        model = Budget
        fields = ["name", "year", "currency"]
        labels = {
            "name": "Име на бюджет",
            "currency": "Валута",
        }
        widgets = {
            "currency": forms.Select(attrs={"class": "form-select"}),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)

        year = int(self.cleaned_data["year"])
        instance.date_from = datetime.date(year, 1, 1)
        instance.date_to = datetime.date(year, 12, 31)

        if commit:
            instance.save()
        return instance


class BudgetItemForm(forms.ModelForm):
    class Meta:
        model = BudgetItem
        fields = ["category", "planned_amount"]
        widgets = {
            "category": forms.Select(attrs={"class": "form-select"}),
            "planned_amount": forms.NumberInput(attrs={"class": "form-control"}),
        }

# форма за одобрение
class BudgetApprovalForm(forms.Form):
    approve = forms.BooleanField(required=True, label="Одобрявам бюджета")
