from django.urls import path
from .views import *

urlpatterns = [
    # path('', reports_home, name='reports_home'),
    path('', ReportsHomeView.as_view(), name='reports_home'),
    path('spending-history/', spending_history, name='spending_history'),

]