from django.urls import path
from .views import *

urlpatterns = [
    path('', recipe_list, name='recipe_list'),
    path('recipes/create/', create_recipe, name='create_recipe'),
    path('recipes/save/', save_recipe, name='save_recipe'),
    path('recipes/cook/<int:recipe_id>/', cook_recipe, name='cook_recipe'),
    path('recipes/generate-shopping/<int:recipe_id>/', generate_recipe_shopping_list, name='generate_recipe_shopping_list'),
    path('recipes/recipe_view/<int:recipe_id>/', recipe_view, name='recipe_view'),
    path('cooking-home/', cooking_home, name='cooking_home'),

    path('favourites/', favourite_groups_list, name='favourite_recipes'),
    path('favourites/create/', create_favourite_group, name='create_favourite_group'),
    path('favourites/<int:group_id>/', favourite_group_detail, name='favourite_group_detail'),
    path('favourites/<int:group_id>/add/<int:recipe_id>/', add_recipe_to_group, name='add_recipe_to_group'),
    path('favourites/create/ajax/', create_favourite_group_ajax, name='create_favourite_group_ajax'),
    path('favourites/add-recipe/ajax/', add_recipe_to_group_ajax, name='add_recipe_to_group_ajax'),
    path('favourites/<int:group_id>/update-name/', update_group_name_ajax, name='update_group_name_ajax'),
    path('favourites/<int:group_id>/remove/<int:recipe_id>/', remove_recipe_from_group_ajax, name='remove_recipe_from_group_ajax'),
    path('favourites/<int:group_id>/delete/', delete_group_ajax, name='delete_group_ajax'),
    path('favourites/<int:group_id>/shopping-list/', generate_group_shopping_list, name='generate_group_shopping_list'),





]