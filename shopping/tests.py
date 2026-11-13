from django.test import TestCase
from .models import Product, ProductCategory, MainCategory
from .forms import CreateProductForm

# Create your tests here.


class ProductCategoryTestCase(TestCase):
    def test_create_product_category(self):
        category = ProductCategory.objects.create(name = 'Битови сметки')
        self.assertEqual(str(category), 'Битови сметки')
        self.assertIsNone(category.main_category)


class ProductTestCase(TestCase):
    def setUp(self):
        self.main_category = MainCategory.objects.create(name='Test Main Category')
        self.category = ProductCategory.objects.create(name='Test Subcategory', main_category=self.main_category)
    def test_create_product_success(self):
        product = Product.objects.create(
            name = 'Test Product 1',
            category = self.category,
            calories = 100,
            suitable_for_cooking=True
        )
        self.assertEqual(str(product), 'Test Product 1 - Test Subcategory (Test Main Category)')

    def test_create_product_calories_mandatory(self):
        form_data = {
            'name': 'Test Product',
            'category': self.category.id,
            'suitable_for_cooking': True,
            'calories': '',
        }
        form = CreateProductForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('Калории са задължителни, ако продукта става за готвене', form.errors['__all__'])

    def test_name_and_category_required(self):
        form_data = {
            'suitable_for_cooking': False,
            'calories': 50,
        }
        form = CreateProductForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('Име и категория са задължителни!', form.errors['__all__'])



class AddProductAccessTest(TestCase):
    def test_add_product_requires_login(self):
        category = ProductCategory.objects.create(name='Test Subcategory')
        response = self.client.post('/shopping/add_product/', {'name': 'Spam product', 'category': category.id,
                                                               'calories': 1})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith('/users/please-login/'))
        self.assertFalse(Product.objects.filter(name='Spam product').exists())


class CachedPriceTest(TestCase):
    def test_value_is_fetched_once_and_failures_are_remembered_briefly(self):
        from unittest import mock
        from .helpers import cached_price
        ok = mock.Mock(return_value=0.25)
        self.assertEqual(cached_price('test-ok', ok), 0.25)
        self.assertEqual(cached_price('test-ok', ok), 0.25)
        self.assertEqual(ok.call_count, 1)

        for failing in (mock.Mock(side_effect=RuntimeError('site down')), mock.Mock(return_value='no data')):
            name = f'test-fail-{id(failing)}'
            self.assertIsNone(cached_price(name, failing))
            self.assertIsNone(cached_price(name, failing))
            self.assertEqual(failing.call_count, 1)
