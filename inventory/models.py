from decimal import Decimal

from django.db import models

from shopping.models import Product, ProductCategory
from users.models import CustomUser, HouseHold


class BaseInventoryProduct(models.Model):
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='inventory_product')
    category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='inventory_category')
    quantity = models.DecimalField(max_digits=10, decimal_places=3, default=0.000)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    average_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    daily_consumption = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    minimum_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    inventory_related = models.BooleanField(default=True)

    class Meta:
        abstract = True

    def average_price_now(self):
        """amount / quantity, rounded to cents; 0 when there is no stock."""
        quantity, amount = Decimal(str(self.quantity)), Decimal(str(self.amount))
        return (amount / quantity).quantize(Decimal('0.01')) if quantity > 0 else Decimal('0.00')

    def calculate_average_price(self):
        self.average_price = self.average_price_now()
        self.save()


class BaseProductCategory(models.Model):
    product_category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='user_product_category')
    direct_planning = models.BooleanField(default=False)
    daily_consumption = models.DecimalField(max_digits=10, decimal_places=3, default=0.000)
    minimum_quantity = models.DecimalField(max_digits=10, decimal_places=3, default=0.000)

    class Meta:
        abstract = True


class InventoryProduct(BaseInventoryProduct):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)


    @staticmethod
    def bulk_update_inventory(data, user):
        """Update the given rows ({id: {field: value}}) - only rows that belong to `user`."""
        products = list(InventoryProduct.objects.filter(id__in=data.keys(), user=user))
        for product in products:
            updates = data[str(product.id)]
            product.quantity = updates.get("quantity", product.quantity)
            product.amount = updates.get("amount", product.amount)
            product.daily_consumption = updates.get("daily_consumption", product.daily_consumption)
            product.minimum_quantity = updates.get("minimum_quantity", product.minimum_quantity)
            product.inventory_related = updates.get("inventory_related", product.inventory_related)
            product.average_price = product.average_price_now()      # saved once, by bulk_update below

        InventoryProduct.objects.bulk_update(products, ["quantity", "amount", "average_price", "daily_consumption",
                                                        "minimum_quantity", "inventory_related"])

    def __str__(self):
        return f"{self.product.name} - {self.quantity} units - Avg Price: {self.average_price}"


class UserProductCategory(BaseProductCategory):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

    def __str__(self):
        return self.product_category.name


class HouseholdInventoryProduct(BaseInventoryProduct):
    household = models.ForeignKey(HouseHold, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='household_inventory_product')
    category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='household_inventory_category')

    @staticmethod
    def bulk_update_inventory(data, household):
        """Update the given rows ({id: {field: value}}) - only rows that belong to `household`."""
        products = list(HouseholdInventoryProduct.objects.filter(id__in=data.keys(), household=household))
        for product in products:
            updates = data[str(product.id)]
            product.quantity = updates.get("quantity", product.quantity)
            product.amount = updates.get("amount", product.amount)
            product.daily_consumption = updates.get("daily_consumption", product.daily_consumption)
            product.minimum_quantity = updates.get("minimum_quantity", product.minimum_quantity)
            product.inventory_related = updates.get("inventory_related", product.inventory_related)
            product.average_price = product.average_price_now()      # saved once, by bulk_update below

        HouseholdInventoryProduct.objects.bulk_update(
            products,
            ["quantity", "amount", "average_price", "daily_consumption", "minimum_quantity", "inventory_related"]
        )

    def __str__(self):
        return f"{self.product.name} (Household: {self.household.name}) — {self.quantity} units @ Avg {self.average_price}"


class HouseholdProductCategory(BaseProductCategory):
    household = models.ForeignKey(HouseHold, on_delete=models.CASCADE)
    product_category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='household_product_category')
