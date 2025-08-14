from django.urls import path
from .views import *

urlpatterns = [
    path('', finance_home, name='finance_home'),
    path('news/', finance_news, name='news'),
    path('markets/', markets, name='markets'),
    path('portfolio/', portfolio, name='portfolio'),
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
]
