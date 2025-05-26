from django.contrib import admin
from .models import *

# Register your models here.
@admin.register(MainCategory)
class MainCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'main_category')


class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'available_stock', 'category', 'image')
    fields = ('name', 'category', 'price', 'available_stock', 'image')

admin.site.register(Product, ProductAdmin)

@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Shopping)
class ShoppingAdmin(admin.ModelAdmin):
    list_display = ('date', 'shop')

@admin.register(ShoppingProduct)
class ShoppingProductAdmin(admin.ModelAdmin):
    list_display = ('product', 'quantity', 'price', 'discount', 'amount')