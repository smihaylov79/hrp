from django.urls import path
from .views import *

urlpatterns = [
    path('', finance_home, name='finance_home'),
    path('news/', finance_news, name='news'),
    path('markets/', markets, name='markets'),
    path('portfolio/', portfolio_home, name='portfolio'),
    path('screener/', screener_view, name='screener'),
    path('finance/ticker/<str:ticker>/', ticker_details, name='ticker-details'),
    path('delete-latest-data/', delete_last_data, name='delete_last_data'),
    path('trade/', trade, name='trade'),
    path('invest/', invest, name='invest'),
    path('trade-details/', trade_details, name='trade_details'),
    path('symbol-details/', symbol_details, name='symbol_details'),
    path('delete-latest-data-invest/', delete_last_data_invest, name='delete_last_data_invest'),
    path('invest-details/', invest_details, name='invest_details'),
    path('screener-settings/', screener_settings, name='screener_settings'),
    path('check-margin/<str:symbol>', check_margin, name='check_margin'),
    path("predict-price/", predict_price_view, name="predict_price"),
    path("predict/", prediction_page, name="prediction_page"),
    path('portfolio-details/<int:portfolio_id>/', portfolio_details, name='portfolio_details'),
    # path('portfolio-create/', portfolio_create, name='portfolio_create'),
    # path('portfolio-edit/<int:portfolio_id>', portfolio_edit, name='portfolio_edit'),
    # path('symbol_add/<int:portfolio_id>', symbol_add, name='symbol_add'),
    path('symbol-remove/<int:symbol_id>/', symbol_remove, name='symbol_remove'),
    path('portfolio/create/ajax/', portfolio_create_ajax, name='portfolio_create_ajax'),
    path('portfolio/edit/ajax/', portfolio_edit_ajax, name='portfolio_edit_ajax'),
    path('symbol/add/ajax/', symbol_add_ajax, name='symbol_add_ajax'),
    path('symbol/edit/ajax/', symbol_edit_ajax, name='symbol_edit_ajax'),
    path('symbol/add-to-portfolio/', add_symbol_to_portfolio, name='add_symbol_to_portfolio'),
    path('predict-gainers-loosers/', gainers_loosers_prediction_view, name='gainers_loosers_prediction_view'),




]
