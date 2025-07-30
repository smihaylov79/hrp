from django.urls import path
from .views import *

urlpatterns = [
    path('', finance_home, name='finance_home'),
    path('news/', finance_news, name='news'),
    path('markets/', markets, name='markets'),
    path('portfolio/', portfolio, name='portfolio'),
    path('screener/', screener, name='screener'),
    path('finance/ticker/<str:ticker>/', ticker_details, name='ticker-details'),
    path('delete-latest-data/', delete_last_data, name='delete_last_data'),
    path('trade/', trade, name='trade'),
    path('invest/', invest, name='invest'),
    path('trade-details/', trade_details, name='trade_details'),
    path('symbol-details/', symbol_details, name='symbol_details'),
]
