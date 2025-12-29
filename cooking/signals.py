from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import RecipeIngredient

@receiver(post_save, sender=RecipeIngredient)
def update_recipe_calories_on_save(sender, instance, **kwargs):
    instance.recipe.update_total_calories()

@receiver(post_delete, sender=RecipeIngredient)
def update_recipe_calories_on_delete(sender, instance, **kwargs):
    instance.recipe.update_total_calories()
