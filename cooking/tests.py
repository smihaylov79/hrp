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


class RecipeCatalogueTests(TestCase):
    """The recipe catalogue is cached for everybody; cost/availability stay per user; pages do not run N+1 queries."""

    @classmethod
    def setUpTestData(cls):
        from .models import UserFavouriteRecipe
        cls.owner = CustomUser.objects.create_user(email='owner@user.com', password='Ineedstrongpassord123!@',
                                                   first_name='Owner', last_name='user')
        cls.other = CustomUser.objects.create_user(email='other@user.com', password='Ineedstrongpassord123!@',
                                                   first_name='Other', last_name='user')
        product_cat = ProductCategory.objects.create(name='Test subcat')
        cls.category = RecipeCategory.objects.create(name='Супи')
        cls.products = [Product.objects.create(name=f'Продукт {i}', category=product_cat, suitable_for_cooking=True)
                        for i in range(8)]
        cls.recipes = []
        for i in range(12):
            recipe = Recipe.objects.create(name=f'Рецепта {i}', category=cls.category)
            for product in cls.products[:4]:
                RecipeIngredient.objects.create(recipe=recipe, product=product, quantity=1)
            cls.recipes.append(recipe)
        for product in cls.products:       # only the owner has everything, at 2.00 each
            InventoryProduct.objects.create(user=cls.owner, product=product, quantity=5, amount=10, average_price=2)
        group = UserFavouriteRecipe.objects.create(user=cls.owner, name='Меню')
        group.recipes.set(cls.recipes)
        cls.group = group

    def queries_for(self, user, url):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        self.client.force_login(user)
        self.client.get(url)                 # warm the shared cache
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return len(ctx), response

    def test_cooking_pages_stay_under_the_query_budget(self):
        for url in [reverse('recipe_list'), reverse('cooking_home'), reverse('favourite_recipes'),
                    reverse('favourite_group_detail', args=[self.group.id]),
                    reverse('recipe_view', args=[self.recipes[0].id])]:
            with self.subTest(url=url):
                count, _ = self.queries_for(self.owner, url)
                self.assertLessEqual(count, 15, f'{url} ran {count} queries')

    def test_cost_and_availability_are_per_user_although_the_catalogue_is_shared(self):
        _, mine = self.queries_for(self.owner, reverse('recipe_list'))
        _, theirs = self.queries_for(self.other, reverse('recipe_list'))
        self.assertEqual({r.user_cost for r in mine.context['recipes']}, {8})          # 4 ingredients x 2.00
        self.assertTrue(all(r.user_availability for r in mine.context['recipes']))
        self.assertEqual({r.user_cost for r in theirs.context['recipes']}, {0})
        self.assertFalse(any(r.user_availability for r in theirs.context['recipes']))
        self.assertContains(mine, 'Всички продукти налични')
        self.assertNotContains(theirs, 'Всички продукти налични')
        self.assertContains(theirs, 'Other')
        self.assertNotContains(theirs, 'Owner')

    def test_catalogue_is_refreshed_when_a_recipe_changes(self):
        self.client.force_login(self.owner)
        self.assertNotContains(self.client.get(reverse('recipe_list')), 'Нова рецепта')
        recipe = Recipe.objects.create(name='Нова рецепта', category=self.category)
        self.assertContains(self.client.get(reverse('recipe_list')), 'Нова рецепта')
        recipe.name = 'Преименувана'
        recipe.save()
        self.assertContains(self.client.get(reverse('recipe_list')), 'Преименувана')
        recipe.delete()
        self.assertNotContains(self.client.get(reverse('recipe_list')), 'Преименувана')

    def test_filters_work_on_the_cached_catalogue(self):
        other_category = RecipeCategory.objects.create(name='Десерти')
        dessert = Recipe.objects.create(name='Торта', category=other_category)
        RecipeIngredient.objects.create(recipe=dessert, product=self.products[7], quantity=1)
        self.client.force_login(self.owner)
        by_category = self.client.get(reverse('recipe_list'), {'category': 'Десерти'})
        self.assertEqual([r.name for r in by_category.context['recipes']], ['Торта'])
        by_ingredient = self.client.get(reverse('recipe_list'), {'ingredient': self.products[7].id})
        self.assertEqual([r.name for r in by_ingredient.context['recipes']], ['Торта'])
        self.assertEqual(by_ingredient.context['product'], self.products[7])
        self.assertEqual(self.client.get(reverse('recipe_list'), {'ingredient': 'abc'}).status_code, 200)

    def test_anonymous_visitor_can_browse_recipes(self):
        self.client.logout()
        response = self.client.get(reverse('recipe_list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['recipes']), 12)
