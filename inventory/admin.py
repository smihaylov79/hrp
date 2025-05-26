from django.contrib import admin
from .models import InventoryProduct
# Register your models here.

@admin.register(InventoryProduct)
class InventoryProductAdmin(admin.ModelAdmin):
    list_display = ('product__name', 'quantity', 'amount', 'average_price', 'daily_consumption', 'minimum_quantity')
