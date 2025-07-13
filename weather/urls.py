from django.urls import path
from .views import *

urlpatterns = [
    path('forecast/<str:date>/', detailed_forecast, name='detailed-forecast'),
    path('set-location/', set_location, name='set_location'),
    ]