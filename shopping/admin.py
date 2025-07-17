from django.contrib import admin
from .models import *

# Register your models here.
@admin.register(MainCategory)
class MainCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'main_category')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'available_stock', 'category', 'image')
    fields = ('name', 'category', 'price', 'available_stock', 'image')


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(Shopping)
class ShoppingAdmin(admin.ModelAdmin):
    list_display = ('date', 'shop')
    search_fields = ('shopping_products__product__name',)


@admin.register(ShoppingProduct)
class ShoppingProductAdmin(admin.ModelAdmin):
    list_display = ('shopping__user__first_name', 'product', 'quantity', 'price', 'discount', 'amount', 'not_for_household')
    search_fields = ('product__name', )
    list_filter = ('shopping__user__first_name',)



@admin.register(ShoppingList)
class ShoppingListAdmin(admin.ModelAdmin):
    list_display = ('user__first_name', 'date_generated', 'executed', 'items')


@admin.register(RecipeShoppingList)
class RecipeShoppingListAdmin(admin.ModelAdmin):
    ...
