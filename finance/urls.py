from django.urls import path
from .views import *

urlpatterns = [
    path('', finance_home, name='finance_home'),
]