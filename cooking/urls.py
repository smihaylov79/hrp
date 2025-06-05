from django.urls import path
from .views import *

urlpatterns = [
    path('', recipe_list, name='recipe_list'),
    path('recipes/create/', create_recipe, name='create_recipe'),
    path('recipes/save/', save_recipe, name='save_recipe'),
    path('recipes/cook/<int:recipe_id>/', cook_recipe, name='cook_recipe'),
    path('recipes/generate-shopping/<int:recipe_id>/', generate_recipe_shopping_list, name='generate_recipe_shopping_list'),
    path('recipes/recipe_view/<int:recipe_id>/', recipe_view, name='recipe_view'),
]