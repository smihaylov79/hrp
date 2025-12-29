from django.urls import path
from .views import *

urlpatterns = [
    path("", budget_home, name="budget_home"),
    path("propose/", propose_budget, name="propose_budget"),
    path("<int:pk>/", budget_detail, name="budget_detail"),
    path("<int:pk>/track/", track_budget, name="track_budget"),
    path("<int:pk>/edit/", edit_budget, name="edit_budget"),
]
