"""Shared, query-light helpers for the cooking pages.

The recipe catalogue (recipes + category + ingredients + products) is the same for every user, so it is
cached; cost and availability depend on the user's inventory and are computed per request from one query.
Never cache anything that depends on the user here.
"""
from django.core.cache import cache
from django.db.models import Count
from django.db.models.signals import post_delete, post_save

from inventory.models import HouseholdInventoryProduct, InventoryProduct
from shopping.models import Product

from .models import Recipe, RecipeCategory, RecipeIngredient

CATALOGUE_KEY = "cooking:catalogue"
CATEGORIES_KEY = "cooking:categories"
CACHE_SECONDS = 60 * 60     # safety net for changes that bypass signals (bulk updates, raw SQL)


def recipe_catalogue():
    """Every recipe with its category and ingredients (and their products) loaded. User independent."""
    recipes = cache.get(CATALOGUE_KEY)
    if recipes is None:
        recipes = list(
            Recipe.objects.select_related("category")
            .prefetch_related("recipe_ingredients__product")
            .order_by("category__name", "id")
        )
        cache.set(CATALOGUE_KEY, recipes, CACHE_SECONDS)
    return recipes


def recipe_categories():
    """Recipe categories with ``recipe_count``. User independent."""
    categories = cache.get(CATEGORIES_KEY)
    if categories is None:
        categories = list(RecipeCategory.objects.annotate(recipe_count=Count("recipes")))
        cache.set(CATEGORIES_KEY, categories, CACHE_SECONDS)
    return categories


def invalidate_catalogue(**kwargs):
    cache.delete_many([CATALOGUE_KEY, CATEGORIES_KEY])


for _model in (Recipe, RecipeIngredient, RecipeCategory, Product):
    post_save.connect(invalidate_catalogue, sender=_model, dispatch_uid=f"cooking_catalogue_save_{_model.__name__}")
    post_delete.connect(invalidate_catalogue, sender=_model,
                        dispatch_uid=f"cooking_catalogue_delete_{_model.__name__}")


def user_inventory_queryset(user):
    """Inventory rows of the user's household, or of the user; empty for anonymous users."""
    if user is None or not user.is_authenticated:
        return InventoryProduct.objects.none()
    if user.household_id:
        return HouseholdInventoryProduct.objects.filter(household_id=user.household_id)
    return InventoryProduct.objects.filter(user=user)


def inventory_maps(user):
    """({product_id: average price}, {product_id: quantity}) for the user's inventory - one query."""
    prices, quantities = {}, {}
    for product_id, quantity, average_price in user_inventory_queryset(user).values_list(
            "product_id", "quantity", "average_price"):
        prices[product_id] = average_price
        quantities[product_id] = quantity
    return prices, quantities


def recipe_cost(recipe, prices):
    """Cost of a recipe from the user's average prices. Uses the prefetched ingredients."""
    return round(sum(prices.get(ing.product_id, 0) * ing.quantity for ing in recipe.recipe_ingredients.all()), 2)


def missing_ingredients(recipe, quantities):
    """Number of ingredients the user does not have enough of."""
    return sum(1 for ing in recipe.recipe_ingredients.all() if quantities.get(ing.product_id, 0) < ing.quantity)
