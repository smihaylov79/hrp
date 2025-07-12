from django.urls import path
from .views import *

urlpatterns = [
    # path('', reports_home, name='reports_home'),
    path('', ReportsHomeView.as_view(), name='reports_home'),
    path('spending-history/', SpendingsView.as_view(), name='spendings_history'),
    path('product-price-history/', product_price_history, name='product_price_history'),
    path('spendings-by-shop/', spendings_by_shop, name='spendings_by_shop'),

]