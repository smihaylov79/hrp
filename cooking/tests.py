from django.test import TestCase, RequestFactory
from unittest.mock import MagicMock
from django.urls import reverse

from .models import RecipeCategory, Recipe, RecipeIngredient
from users.models import CustomUser
from inventory.models import InventoryProduct
from shopping.models import Product, ProductCategory, MainCategory, RecipeShoppingList
from .views import cook_recipe, generate_recipe_shopping_list


# Create your tests here.

class RecipeTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(email='test@user.com', password='Ineedstrongpassord123!@',
                                                   first_name='test', last_name='user')

        self.main_cat = MainCategory.objects.create(name='Test Main')
        self.product_cat = ProductCategory.objects.create(name='Test subcat', main_category=self.main_cat)
        self.product_1 = Product.objects.create(name='Test Product 1', category=self.product_cat, calories=20, suitable_for_cooking=True)
        self.product_2 = Product.objects.create(name='Test Product 2', category=self.product_cat, calories=20,
                                                suitable_for_cooking=True)

        self.recipe_category = RecipeCategory.objects.create(name='Салата')
        self.recipe = Recipe.objects.create(category=self.recipe_category)
        RecipeIngredient.objects.create(recipe=self.recipe, product=self.product_1, quantity=2)
        RecipeIngredient.objects.create(recipe=self.recipe, product=self.product_2, quantity=3)
        InventoryProduct.objects.create(user=self.user, product=self.product_1, quantity=10, amount=10, average_price=1)
        InventoryProduct.objects.create(user=self.user, product=self.product_2, quantity=0, amount=0, average_price=0)

    def test_cook_recipe_inventory_update(self):
        factory = RequestFactory()
        request = factory.get(reverse('cook_recipe', args=[self.recipe.id]))
        request.user = self.user

        response = cook_recipe(request, self.recipe.id)

        inventory = InventoryProduct.objects.get(user=self.user, product=self.product_1)
        self.assertEqual(inventory.quantity, 8)
        self.assertEqual(inventory.amount, 8 * inventory.average_price)


    def test_recipe_shopping_list_generated(self):
        factory = RequestFactory()
        request = factory.get(reverse('generate_recipe_shopping_list', args=[self.recipe.id]))
        request.user = self.user
        request._messages = MagicMock()

        response = generate_recipe_shopping_list(request, self.recipe.id)
        item_obj = RecipeShoppingList.objects.filter(user=self.user).first()
        self.assertIsNotNone(item_obj)
        self.assertIn('Test Product 2', item_obj.items)




