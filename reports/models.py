from django.db import models

from inventory.models import InventoryProduct, HouseholdInventoryProduct
from users.models import CustomUser, HouseHold


# Create your models here.


class ExchangeRate(models.Model):
    base_currency = models.CharField(max_length=3)
    target_currency = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=12, decimal_places=7)
    date_extracted = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = (('base_currency', 'target_currency', 'date_extracted'),)

    def __str__(self):
        return f'{self.base_currency} -> {self.target_currency} - {self.date_extracted}: {self.rate}'


class UserInflationBasket(models.Model):
    name = models.CharField(max_length=100, unique=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)


class UserInflationBasketItem(models.Model):
    basket = models.ForeignKey(UserInflationBasket, on_delete=models.CASCADE, related_name='user_basket_items')
    product = models.ForeignKey(InventoryProduct, on_delete=models.CASCADE)


class HouseholdInflationBasket(models.Model):
    name = models.CharField(max_length=100, unique=True)
    household = models.ForeignKey(HouseHold, on_delete=models.CASCADE)


class HouseholdInflationBasketItem(models.Model):
    basket = models.ForeignKey(HouseholdInflationBasket, on_delete=models.CASCADE, related_name='household_basket_items')
    product = models.ForeignKey(HouseholdInventoryProduct, on_delete=models.CASCADE)


