from django import forms
from shopping.models import *
from django.utils.timezone import localdate
from .models import *


class SpendingsReportFilterForm(forms.Form):
    SPENDINGS_CHOICES = [
        ("all", "Всички"),
        ("household", "Само за домакинството"),
        ("external", "Само извън домакинството"),
        ]

    main_category = forms.ModelChoiceField(
        queryset=MainCategory.objects.all(),
        required=False,
        label='Категория',
    )
    date_from = forms.DateField(required=False,
                                label="От",
                                widget=forms.DateInput(attrs={'type': 'date'})
                                )
    date_to = forms.DateField(required=False,
                              label="До",
                              widget=forms.DateInput(attrs={'type': 'date'}))

    currency = forms.ChoiceField(choices = CurrencyChoice.choices, required=False, label = "Валута")

    not_for_household_filter = forms.ChoiceField(
        choices=SPENDINGS_CHOICES,
        required=False,
        label="Филтър за домакинство"
    )
    shops = forms.ModelMultipleChoiceField(
        queryset=Shop.objects.none(),  # default, updated in __init__
        required=False,
        label="Магазини",
        widget=forms.SelectMultiple(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        user_shops = kwargs.pop('user_shops', Shop.objects.none())
        super().__init__(*args, **kwargs)
        self.fields['shops'].queryset = user_shops

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('date_to'):
            cleaned_data['date_to'] = localdate()
        return cleaned_data
