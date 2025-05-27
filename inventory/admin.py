from django.contrib import admin
from .models import InventoryProduct, UserProductCategory
# Register your models here.

@admin.register(InventoryProduct)
class InventoryProductAdmin(admin.ModelAdmin):
    list_display = ('product__name', 'quantity', 'amount', 'average_price', 'daily_consumption', 'minimum_quantity')


@admin.register(UserProductCategory)
class UserProductCategory(admin.ModelAdmin):
    list_display = ('user__first_name', 'product_category', 'direct_planning', 'daily_consumption', 'minimum_quantity')

