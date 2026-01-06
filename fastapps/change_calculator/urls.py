from django.urls import path
from .views import change_calculator_view

urlpatterns = [
    path("", change_calculator_view, name="change_calculator"),
]
