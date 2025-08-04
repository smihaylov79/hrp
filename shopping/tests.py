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

