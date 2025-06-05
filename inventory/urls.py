from django.urls import path
from .views import *

urlpatterns = [
    path('', inventory_list, name='inventory'),  # Ensure correct naming
    path('update_inventory/', update_inventory, name='update_inventory'),
    path("categories/", user_category_settings, name="user_category_settings"),
    path("reports/", inventory_reports, name="inventory_reports"),
    path("generate_shopping_list/", generate_shopping_list, name="generate_shopping_list"),
    path("inventory/shopping_list/<int:list_id>/", shopping_list_view, name="shopping_list_view"),
    path("shopping_list/<int:list_id>/update/", update_shopping_list, name="update_shopping_list"),
    path("shopping_list/<int:list_id>/send/", send_shopping_list, name="send_shopping_list"),
    path("shopping_lists/", all_shopping_lists, name="all_shopping_lists"),
    path("recipe_shopping_list/<int:list_id>/", recipe_shopping_list_view, name="recipe_shopping_list_view"),
    path("recipe_shopping_list/<int:list_id>/send/", send_recipe_shopping_list, name="send_recipe_shopping_list"),
    path("price-history/", product_price_history, name="product_price_history"),
]
