from django import forms

from shopping.models import CurrencyChoice

# CURRENCIES = [
#     ("EUR", "€"),
#     ("BGN", "лв."),
# ]

class ChangeCalculatorForm(forms.Form):
    paid_amount = forms.DecimalField(
        label="Платена сума",
        min_value=0,
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )

    paid_currency = forms.ChoiceField(
        choices=CurrencyChoice.choices,
        widget=forms.Select(attrs={"class": "form-select"})
    )

    bill_amount = forms.DecimalField(
        label="Сметка",
        min_value=0,
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )

    bill_currency = forms.ChoiceField(
        choices=CurrencyChoice.choices,
        widget=forms.Select(attrs={"class": "form-select"})
    )

