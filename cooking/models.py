from django.db import models
from shopping.models import Product
from inventory.models import *
from users.models import *


# Create your models here.


class RecipeCategory(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name


class Recipe(models.Model):
    name = models.CharField(max_length=150)
    category = models.ForeignKey(RecipeCategory, on_delete=models.CASCADE, related_name='recipes')
    time_to_prepare = models.IntegerField(null=True, blank=True, default=0)
    instructions = models.TextField(null=True, blank=True)
    url_link = models.URLField(null=True, blank=True)
    ingredients = models.ManyToManyField(Product, through='RecipeIngredient', related_name='recipes')
    image = models.ImageField(upload_to='recipe_images/', null=True, blank=True)

    total_calories = models.IntegerField(default=0)

    def check_availability(self, user):
        """"OK" when the user has enough of every ingredient (see cooking/services.py)."""
        from .services import inventory_maps, missing_ingredients
        _prices, quantities = inventory_maps(user)
        return "OK" if missing_ingredients(self, quantities) == 0 else "Липсващи продукти"

    def calculate_cost(self, user):
        """Cost of the recipe at the user's average prices (see cooking/services.py)."""
        from .services import inventory_maps, recipe_cost
        prices, _quantities = inventory_maps(user)
        return recipe_cost(self, prices)

    def update_total_calories(self):
        ingredients = self.recipe_ingredients.select_related("product")
        self.total_calories = sum(
            ing.product.calories * ing.quantity
            for ing in ingredients
        )
        self.save(update_fields=["total_calories"])

    # def calculate_calories(self):
    #     total_calories = sum(ingredient.product.calories * ingredient.quantity for ingredient in self.recipe_ingredients.all())
    #     return round(total_calories, 0)

    def __str__(self):
        return self.name


class RecipeIngredient(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='recipe_ingredients')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='recipe_ingredients')
    quantity = models.DecimalField(max_digits=6, decimal_places=3)
    unit = models.CharField(max_length=15, null=True, blank=True)

    def __str__(self):
        return f"{self.quantity} of {self.product.name} in {self.recipe.name}"


class RecipeTimesCooked(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='recipe_times_cooked')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='recipe_times_cooked')
    date = models.DateTimeField(auto_now_add=True)


class HouseholdRecipeTimesCooked(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='household_recipe_times_cooked')
    household = models.ForeignKey(HouseHold, on_delete=models.CASCADE, related_name='household_recipe_times_cooked')
    date = models.DateTimeField(auto_now_add=True)


class UserFavouriteRecipe(models.Model):
    name = models.CharField(max_length=50)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='favourite_groups')
    recipes = models.ManyToManyField(Recipe, through='UserFavoriteRecipeData', related_name='in_favourite_groups')

    def __str__(self):
        return f"{self.name}"


class UserFavoriteRecipeData(models.Model):
    favourite_group = models.ForeignKey(UserFavouriteRecipe, on_delete=models.CASCADE, related_name='entries')
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='favourite_entries')

    def __str__(self):
        return f"{self.recipe.name} in {self.favourite_group.name}"

