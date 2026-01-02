from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from forum.models import Category
from .models import Shopping, Shop, Product, ProductCategory, CurrencyChoice


class BaseShoppingForm(forms.ModelForm):
    class Meta:
        model = Shopping
        fields = ['shop', 'date', 'currency']
        widgets = {
            'shop': forms.Select(attrs={'name': 'shop_id', 'class': 'form-select'}),
            'date': forms.DateInput(attrs={'name': 'date', 'class': 'form-control', 'type': 'date'}),
            'currency': forms.Select(attrs={'name': 'currency', 'class': 'form-select'}),
        }
        labels = {
            'shop': 'Магазин/Доставчик',
            'date': 'Дата на разход',
            'currency': 'Валута'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.fields['date'].initial:
            self.fields['date'].initial = timezone.localdate()
        if not self.instance.pk:
            self.fields['currency'].initial = CurrencyChoice.EUR


class UtilityBillForm(BaseShoppingForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['shop'].queryset = Shop.objects.filter(utility_supplier=True).order_by('name')


class RegularShoppingForm(BaseShoppingForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        shops = Shop.objects.all().order_by('name')
        self.fields['shop'].queryset = shops
        if shops.exists():
            self.fields['shop'].initial = shops.first()


class CreateProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['category', 'name', 'suitable_for_cooking', 'calories', 'image']
        labels = {
            'category': 'Категория', 'name': 'Име', 'suitable_for_cooking': 'Става за готвене', 'calories': 'Калории', 'image': 'Снимка'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = ProductCategory.objects.all().order_by('name')

    def clean(self):
        cleaned_data = super().clean()
        suitable = cleaned_data.get('suitable_for_cooking')
        calories = cleaned_data.get('calories')
        category = cleaned_data.get('category')
        name = cleaned_data.get('name')
        if suitable and not calories:
            raise ValidationError('Калории са задължителни, ако продукта става за готвене')
        if not category or not name:
            raise ValidationError('Име и категория са задължителни!')
