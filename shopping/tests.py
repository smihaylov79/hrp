from django.test import TestCase

from hrp.testing import HrpTestCase, make_purchase
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


class ShoppingLogicTests(HrpTestCase):
    """Phase 7: inventory rows, prefill prices and totals of purchases."""

    def save_purchase(self, user, product, quantity=1, price=2, not_for_household=False):
        from datetime import date
        from .helpers import save_shopping_products
        from .models import Shop, Shopping
        shopping = Shopping.objects.create(user=user, date=date.today(), shop=Shop.objects.first(), currency='EUR')
        save_shopping_products([{'product_id': product.id, 'quantity': str(quantity), 'price': str(price),
                                 'discount': '', 'not_for_household': not_for_household}],
                               shopping, user, user.household)
        return shopping

    def test_changing_a_products_category_does_not_duplicate_its_inventory_row(self):
        from inventory.models import HouseholdInventoryProduct, InventoryProduct
        for user, model, owner in [(self.alice, InventoryProduct, {'user': self.alice}),
                                   (self.carol, HouseholdInventoryProduct, {'household': self.household})]:
            with self.subTest(user=user.email):
                product = Product.objects.create(name=f'Сирене {user.first_name}', category=self.cat_dairy)
                self.save_purchase(user, product, quantity=2, price=3)
                product.category = self.cat_clean
                product.save()
                self.save_purchase(user, product, quantity=1, price=6)
                row = model.objects.get(product=product, **owner)                  # exactly one row
                self.assertEqual((row.quantity, row.amount, row.category), (3, 12, self.cat_clean))
                self.assertEqual(row.average_price, 4)

    def test_existing_duplicate_rows_do_not_break_saving_a_purchase(self):
        from inventory.models import InventoryProduct
        first = self.user_inventory(self.alice, self.milk, quantity=1, amount=1)
        InventoryProduct.objects.create(user=self.alice, product=self.milk, category=self.cat_clean, quantity=5, amount=5)
        self.save_purchase(self.alice, self.milk, quantity=2, price=2)
        first.refresh_from_db()
        self.assertEqual(first.quantity, 3)                                        # the oldest row is used
        self.assertEqual(InventoryProduct.objects.filter(user=self.alice, product=self.milk).count(), 2)

    def test_purchase_outside_the_household_does_not_touch_stock(self):
        from inventory.models import InventoryProduct
        self.save_purchase(self.alice, self.milk, quantity=2, price=2, not_for_household=True)
        self.assertEqual(InventoryProduct.objects.get(user=self.alice, product=self.milk).quantity, 0)

    def test_prefill_uses_the_households_last_price_without_a_query_per_item(self):
        from datetime import date
        from django.test import RequestFactory
        from .helpers import load_prefill_data
        from .models import HouseholdShoppingList
        products = [Product.objects.create(name=f'Артикул {i}', category=self.cat_dairy) for i in range(6)]
        for index, product in enumerate(products):
            make_purchase(self.dave, product, price=index + 1, on_date=date(2026, 1, 1))     # another member
        make_purchase(self.carol, products[0], price=9, on_date=date(2026, 2, 1))             # newer price
        make_purchase(self.bob, products[1], price=500, on_date=date(2026, 3, 1))             # not in the household
        shopping_list = HouseholdShoppingList.objects.create(
            household=self.household, items=[f'{p.name} (1.00 €)' for p in products] + ['Няма такъв продукт'])
        request = RequestFactory().get('/', {'list': shopping_list.id})
        with self.assertNumQueries(3):                    # the list, the products, their last prices
            data = load_prefill_data(request, self.carol, self.household)
        self.assertEqual([float(row['price']) for row in data], [9, 2, 3, 4, 5, 6])
        self.assertEqual(load_prefill_data(RequestFactory().get('/', {'list': 'abc'}), self.carol, self.household), [])

    def test_prefill_cannot_load_another_households_list(self):
        from django.test import RequestFactory
        from .helpers import load_prefill_data
        from .models import HouseholdShoppingList, ShoppingList
        foreign = HouseholdShoppingList.objects.create(household=self.household, items=['Мляко'])
        self.assertEqual(load_prefill_data(RequestFactory().get('/', {'list': foreign.id}), self.alice, None), [])
        own = ShoppingList.objects.create(user=self.alice, items=['Мляко (1.00 €)'])
        data = load_prefill_data(RequestFactory().get('/', {'list': own.id}), self.alice, None)
        self.assertEqual([row['name'] for row in data], ['Мляко'])

    def test_list_shows_the_total_of_each_purchase_including_discounts(self):
        from decimal import Decimal
        item = make_purchase(self.alice, self.milk, price=10, quantity=2)
        item.discount = Decimal('3')
        item.save()
        from .models import ShoppingProduct
        ShoppingProduct.objects.create(shopping=item.shopping, product=self.soap, quantity=1, price=Decimal('5'))
        make_purchase(self.bob, self.milk, price=999)
        self.client.force_login(self.alice)
        response = self.client.get('/shopping/')
        rows = list(response.context['shoppings'])
        self.assertEqual([row.total for row in rows], [Decimal('22.00')])
        # filtering by one product still shows the whole purchase total
        response = self.client.get('/shopping/', {'product_id': self.soap.id})
        self.assertEqual([row.total for row in response.context['shoppings']], [Decimal('22.00')])
        self.assertEqual(item.shopping.total_amount(), Decimal('22.00'))
        self.assertEqual(item.shopping.total_discount(), Decimal('3.00'))

    def test_shopping_product_amount_without_discount(self):
        from decimal import Decimal
        from datetime import date
        from .models import Shop, Shopping, ShoppingProduct
        shopping = Shopping.objects.create(user=self.alice, date=date.today(), shop=Shop.objects.first())
        item = ShoppingProduct.objects.create(shopping=shopping, product=self.milk, quantity=Decimal('2'), price=Decimal('1.50'))
        self.assertEqual(item.amount, Decimal('3.00'))

    def test_add_product_only_accepts_post(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get('/shopping/add_product/').status_code, 405)
