from django.urls import path
from .views import *

urlpatterns = [
    path('', shopping_list, name='shopping'),
    path('add_to_basket/<int:product_id>/', add_to_basket, name='add_to_basket'),
    path('basket/', basket_view, name='basket'),
    path('update_basket/<int:item_id>/', update_basket, name='update_basket'),
    path('remove_from_basket/<int:item_id>/', remove_from_basket, name='remove_from_basket'),
    path('checkout/', checkout, name='checkout'),
    path('create_shopping/', create_shopping, name='create_shopping'),
    path('save_shopping/', save_shopping, name='save_shopping'),
    path('add_product/', add_product, name='add_product'),
    path('make_shopping/', make_shopping, name='make_shopping'),
    path("shopping/edit/<int:shopping_id>/", edit_shopping, name="edit_shopping"),
]
