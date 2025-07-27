from django.contrib import admin
from django.core.exceptions import ValidationError

from .models import *

# Register your models here.
@admin.register(MainCategory)
class MainCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'main_category')
    list_filter = ('main_category',)
    search_fields = ('name',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'suitable_for_cooking')
    list_filter = ('suitable_for_cooking', 'category__main_category', 'category', )
    search_fields = ('name', )

    def save_model(self, request, obj, form, change):
        if obj.suitable_for_cooking and not obj.calories:
            raise ValidationError("Калории са задължителни, ако продуктът става за готвене.")
        super().save_model(request, obj, form, change)


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('name',)
    list_filter = ('utility_supplier',)
    search_fields = ('name',)


class ShoppingProductsInline(admin.TabularInline):
    model = ShoppingProduct
    extra = 1


@admin.register(Shopping)
class ShoppingAdmin(admin.ModelAdmin):
    list_display = ('date', 'shop')
    search_fields = ('shopping_products__product__name',)
    inlines = [ShoppingProductsInline]


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
