from django.urls import path
from .views import *

urlpatterns = [
    path('', shopping_list, name='shopping'),
    path('regular_shopping/', regular_shopping, name="regular_shopping"),
    path('add_product/', add_product, name='add_product'),
    path("shopping/edit/<int:shopping_id>/", edit_shopping, name="edit_shopping"),
    path("utility_bills/", utility_bills, name="utility_bills"),

]
