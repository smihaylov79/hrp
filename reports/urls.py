from django.urls import path
from .views import *

urlpatterns = [
    path('', ReportsHomeView.as_view(), name='reports_home'),
    path('spending-history/', SpendingsView.as_view(), name='spendings_history'),
    path('by-shop/', SpendingsByShopView.as_view(), name='by_shop'),
    path('price-changes/', price_changes, name='price_changes'),
    path('create-inflation-basket/', create_inflation_basket, name='create_inflation_basket'),
    path('save-inflation-basket/', save_inflation_basket, name='save_inflation_basket'),
    path('edit-inflation-basket/<int:basket_id>', edit_inflation_basket, name='edit_inflation_basket'),
    path('income-analysis/', IncomeView.as_view(), name='income_analysis'),
    path('income-vs-spendings/', income_spendings_comparison, name='income_spendings_comparison'),
    path('consumption-summary/', ConsumptionSummaryView.as_view(), name='consumption_summary'),


]