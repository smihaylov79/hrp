from django.urls import path
from .views import *

urlpatterns = [
    path('', shopping_list, name='shopping'),
    path('save_shopping/', save_shopping, name='save_shopping'),
    path('add_product/', add_product, name='add_product'),
    path('make_shopping/', make_shopping, name='make_shopping'),
    path("shopping/edit/<int:shopping_id>/", edit_shopping, name="edit_shopping"),
    path("utility_bills/", utility_bills, name="utility_bills"),
]
