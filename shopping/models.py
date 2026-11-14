from decimal import Decimal

from django.db import models
from django.db.models import Sum
from django.db.models import TextChoices

from users.models import *


class CurrencyChoice(TextChoices):
    EUR = 'EUR', 'Euro'
    BGN = 'BGN', 'лв.'
    USD = 'USD', 'US Dollar'
    # GBP = 'GBP', 'Pound'


class MainCategory(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        verbose_name_plural = 'Main Categories'

    def __str__(self):
        return self.name


class ProductCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    main_category = models.ForeignKey(MainCategory, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='subcategories')

    class Meta:
        verbose_name_plural = 'Product Categories'

    def __str__(self):
        return f"{self.name} ({self.main_category})" if self.main_category else self.name


class Product(models.Model):
    name = models.CharField(max_length=255, unique=True)
    category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='products')
    image = models.ImageField(upload_to='product_images/', blank=True, null=True)
    calories = models.PositiveIntegerField(default=0, null=True, blank=True)
    suitable_for_cooking = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} - {self.category}"


class Shop(models.Model):
    name = models.CharField(max_length=75)
    utility_supplier = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class Shopping(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='user_shopping', null=True, blank=True,
                             default=None)
    date = models.DateField()
    shop = models.ForeignKey(Shop, on_delete=models.SET_NULL, null=True, blank=True)
    currency = models.CharField(max_length=3, choices=CurrencyChoice.choices, default=CurrencyChoice.BGN)

    class Meta:
        indexes = [
            models.Index(fields=["user", "date"], name="shopping_user_date_idx"),
        ]

    def total_amount(self):
        """Sum of the purchase's lines (after discounts). One query; lists annotate ``total`` instead."""
        return self.shopping_products.aggregate(total=Sum('amount'))['total'] or Decimal('0')

    def total_discount(self):
        return self.shopping_products.aggregate(total=Sum('discount'))['total'] or Decimal('0')

    def __str__(self):
        return f"{self.shop.name} : {self.date}"


class ShoppingProduct(models.Model):
    shopping = models.ForeignKey(Shopping, on_delete=models.CASCADE, related_name="shopping_products")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=3, default=1.00)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    amount = models.DecimalField(max_digits=10, decimal_places=2, editable=False, default=0.00)
    not_for_household = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["product"]),
            models.Index(fields=["shopping"]),
        ]

    def save(self, *args, **kwargs):
        # the field defaults are floats: convert so that a line saved without e.g. a discount still adds up
        self.amount = (Decimal(str(self.quantity)) * Decimal(str(self.price)) - Decimal(str(self.discount or 0)))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} in Shopping {self.shopping.id}"


class BaseShoppingList(models.Model):
    executed = models.BooleanField(default=False)
    items = models.JSONField(default=list)

    class Meta:
        abstract = True


class ShoppingList(BaseShoppingList):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    date_generated = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"Лист за пазаруване на {self.user.first_name} - {self.date_generated}"


class RecipeShoppingList(BaseShoppingList):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    recipe_name = models.CharField(max_length=150)

    def __str__(self):
        return f"Лист за пазаруване на {self.user.first_name} - {self.recipe_name}"


class HouseholdShoppingList(BaseShoppingList):
    household = models.ForeignKey(HouseHold, on_delete=models.CASCADE)
    date_generated = models.DateField(auto_now_add=True)

    def __str__(self):
        return f'Лист за пазаруване на {self.household.name} - {self.date_generated}'


class HouseholdRecipeShoppingList(BaseShoppingList):
    household = models.ForeignKey(HouseHold, on_delete=models.CASCADE)
    recipe_name = models.CharField(max_length=150)

    def __str__(self):
        return f'Лист за пазаруване на {self.household.name} - {self.recipe_name}'
