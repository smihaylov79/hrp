from django.urls import path
from .views import *

urlpatterns = [
    path('', income_home, name='income_home'),
    path('types/', income_type_list, name='income_type_list'),
    path('types/create/', create_income_type, name='create_income_type'),

    path('register/', register_income, name='register_income'),

    ]