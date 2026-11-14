from django.urls import path

from .views import (BudgetView, CashFlowView, CategoriesView, LegacyReportRedirect, OverviewView, PricesView,
                    ShopsView, create_inflation_basket, edit_inflation_basket, save_inflation_basket)

urlpatterns = [
    # the Reports hub: six tabs with one shared filter bar
    path('', OverviewView.as_view(), name='reports_home'),
    path('categories/', CategoriesView.as_view(), name='reports_categories'),
    path('shops/', ShopsView.as_view(), name='reports_shops'),
    path('prices/', PricesView.as_view(), name='reports_prices'),
    path('cash-flow/', CashFlowView.as_view(), name='reports_cash_flow'),
    path('budget/', BudgetView.as_view(), name='reports_budget'),

    # inflation baskets (shown on the "Prices" tab)
    path('create-inflation-basket/', create_inflation_basket, name='create_inflation_basket'),
    path('save-inflation-basket/', save_inflation_basket, name='save_inflation_basket'),
    path('edit-inflation-basket/<int:basket_id>', edit_inflation_basket, name='edit_inflation_basket'),

    # addresses of the old separate report pages -> redirect to the matching tab
    path('spending-history/', LegacyReportRedirect.as_view(target='reports_home'), name='spendings_history'),
    path('consumption-summary/', LegacyReportRedirect.as_view(target='reports_categories'), name='consumption_summary'),
    path('by_category_table/', LegacyReportRedirect.as_view(target='reports_categories'), name='by_category_table'),
    path('by-shop/', LegacyReportRedirect.as_view(target='reports_shops'), name='by_shop'),
    path('price-changes/', LegacyReportRedirect.as_view(target='reports_prices'), name='price_changes'),
    path('income-analysis/', LegacyReportRedirect.as_view(target='reports_cash_flow'), name='income_analysis'),
    path('income-vs-spendings/', LegacyReportRedirect.as_view(target='reports_cash_flow'),
         name='income_spendings_comparison'),
]
