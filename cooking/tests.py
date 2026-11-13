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


class FavouriteGroupCsrfTest(TestCase):
    """The favourites AJAX endpoints change data, so they must be CSRF protected."""

    def setUp(self):
        from django.test import Client
        from .models import UserFavouriteRecipe
        self.user = CustomUser.objects.create_user(email='test@user.com', password='Ineedstrongpassord123!@',
                                                   first_name='test', last_name='user')
        self.group = UserFavouriteRecipe.objects.create(user=self.user, name='Меню')
        self.strict = Client(enforce_csrf_checks=True)
        self.strict.force_login(self.user)
        self.client.force_login(self.user)

    def urls(self):
        return [reverse('create_favourite_group_ajax'), reverse('add_recipe_to_group_ajax'),
                reverse('update_group_name_ajax', args=[self.group.id]),
                reverse('remove_recipe_from_group_ajax', args=[self.group.id, 1]),
                reverse('delete_group_ajax', args=[self.group.id])]

    def test_post_without_csrf_token_is_rejected(self):
        from .models import UserFavouriteRecipe
        for url in self.urls():
            with self.subTest(url=url):
                self.assertEqual(self.strict.post(url, {'name': 'x'}).status_code, 403)
        self.assertEqual(UserFavouriteRecipe.objects.get().name, 'Меню')

    def test_post_with_csrf_header_works(self):
        from .models import UserFavouriteRecipe
        self.strict.get(reverse('favourite_recipes'))            # sets the csrftoken cookie
        token = self.strict.cookies['csrftoken'].value
        response = self.strict.post(reverse('update_group_name_ajax', args=[self.group.id]), {'name': 'Ново'},
                                    headers={'X-CSRFToken': token})
        self.assertEqual(response.json(), {'success': True, 'new_name': 'Ново'})

    def test_recipe_list_is_not_shared_between_users(self):
        """recipe_list used to be cached for 10 minutes for everybody, including the navbar with the user's name."""
        other = CustomUser.objects.create_user(email='other@user.com', password='Ineedstrongpassord123!@',
                                               first_name='Друг', last_name='user')
        first = self.client.get(reverse('recipe_list'))
        self.assertContains(first, 'test')
        self.client.force_login(other)
        second = self.client.get(reverse('recipe_list'))
        self.assertContains(second, 'Друг')
        self.assertNotIn('max-age', second.get('Cache-Control', ''))
