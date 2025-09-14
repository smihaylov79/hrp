from django import forms
from .models import UserPortfolio, UserPortfolioData

class PortfolioForm(forms.ModelForm):
    class Meta:
        model = UserPortfolio
        fields = ['name']


class SymbolAddForm(forms.ModelForm):
    class Meta:
        model = UserPortfolioData
        fields = ['symbol', 'shares', 'price_bought', 'target_price_date_added', 'fair_price_date_added']
