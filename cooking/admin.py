from django.contrib import admin

# Register your models here.
from .models import *


class RecipeIngredientInline(admin.TabularInline):  # Show ingredients as inline table
    model = RecipeIngredient
    extra = 1


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'time_to_prepare')
    search_fields = ("name", "category__name")
    inlines = [RecipeIngredientInline]


@admin.register(RecipeCategory)
class RecipeCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(RecipeIngredient)
class RecipeIngredientAdmin(admin.ModelAdmin):
    list_display = ('recipe', 'product', 'quantity')
    search_fields = ("recipe__name", "product__name")
