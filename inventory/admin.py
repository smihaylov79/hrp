from django.contrib import admin
from .models import InventoryProduct, UserProductCategory, HouseholdInventoryProduct, HouseholdProductCategory


# Register your models here.

@admin.register(InventoryProduct)
class InventoryProductAdmin(admin.ModelAdmin):
    list_display = ('product__name', 'quantity', 'amount', 'average_price', 'daily_consumption', 'minimum_quantity')
    list_filter = ("user", "category")
    search_fields = ("product__name",)


@admin.register(UserProductCategory)
class UserProductCategory(admin.ModelAdmin):
    list_display = ('user__first_name', 'product_category', 'direct_planning', 'daily_consumption', 'minimum_quantity')
    list_filter = ('product_category', )
    search_fields = ('user__first_name', )


@admin.register(HouseholdInventoryProduct)
class HouseholdInventoryAdmin(admin.ModelAdmin):
    list_display = ("product", "household", "quantity", "average_price")
    list_filter = ("household", "category")
    search_fields = ("product__name",)


@admin.register(HouseholdProductCategory)
class HouseholdProductCategoryAdmin(admin.ModelAdmin):
    list_display = ('household__name', 'product_category', 'direct_planning', 'daily_consumption', 'minimum_quantity')