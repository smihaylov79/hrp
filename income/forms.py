from django import forms
from .models import IncomeType, Income


class IncomeTypeForm(forms.ModelForm):
    class Meta:
        model = IncomeType
        fields = ["name"]
        labels = {
            "name": "Вид приход",
        }
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Напр. Заплата, Бонус, Инвестиции"}),
        }


class IncomeForm(forms.ModelForm):
    class Meta:
        model = Income
        fields = ["income_type", "amount", "currency", "date_received", "description"]
        labels = {
            "income_type": "Вид приход",
            "amount": "Сума",
            "currency": "Валута",
            "date_received": "Дата",
            "description": "Описание",
        }
        widgets = {
            "income_type": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "date_received": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Допълнителна информация"}),
        }
