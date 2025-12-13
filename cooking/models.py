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

    def check_availability(self, user):
        household = None
        if user:
            household = user.household
        if household:
            user_inventory = HouseholdInventoryProduct.objects.filter(household=household,
                                                             product__in=[ingredient.product for ingredient in
                                                                          self.recipe_ingredients.all()])
        else:
            user_inventory = InventoryProduct.objects.filter(user=user,
                product__in=[ingredient.product for ingredient in self.recipe_ingredients.all()])
        product_quantity_map = {item.product.id: item.quantity for item in user_inventory}

        for ingredient in self.recipe_ingredients.all():
            if product_quantity_map.get(ingredient.product.id, 0) < ingredient.quantity:
                return "Липсващи продукти"
        return "OK"

    def calculate_cost(self, user):
        household = user.household
        if household:
            user_products = HouseholdInventoryProduct.objects.filter(household=household)
        else:
            user_products = InventoryProduct.objects.filter(user=user)

        product_price_map = {up.product.id: up.average_price for up in user_products}
        total_cost = sum(product_price_map.get(ingredient.product.id, 0) * ingredient.quantity
                         for ingredient in self.recipe_ingredients.all()
                         )
        return round(total_cost, 2)

    def calculate_calories(self):
        total_calories = sum(ingredient.product.calories * ingredient.quantity for ingredient in self.recipe_ingredients.all())
        return round(total_calories, 0)

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

