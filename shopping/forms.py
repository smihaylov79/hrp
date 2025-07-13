from django import forms
from .models import *


class UtilityBillForm(forms.ModelForm):
    class Meta:
        model = Shopping
        fields = ['shop', 'date']
        widgets = {
            'shop': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
        labels = {
            'shop': 'Доставчик',
            'date': 'Дата на фактура'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['shop'].queryset = Shop.objects.filter(utility_supplier=True)