"""Tests of the Phase 8 cleanup commands: cleanup_data and the finance dump / verify / drop sequence."""
import tempfile
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest import skipUnless

from django.core.management import CommandError, call_command
from django.db import IntegrityError, connection, transaction
from django.test import TransactionTestCase

from hrp.testing import HrpTestCase
from inventory.dedupe import merge_duplicates
from inventory.models import HouseholdInventoryProduct, InventoryProduct
from reports.models import (ExchangeRate, HouseholdInflationBasket, HouseholdInflationBasketItem)
from users.finance_removal import finance_tables, find_binary


def run(command, *args, **kwargs):
    out = StringIO()
    call_command(command, *args, stdout=out, **kwargs)
    return out.getvalue()


class CleanupDataTests(HrpTestCase):

    def test_duplicate_rows_cannot_be_created_any_more(self):
        """The database itself now refuses a second row for the same owner and product."""
        self.user_inventory(self.alice, self.milk)
        self.household_inventory(self.household, self.milk)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.user_inventory(self.alice, self.milk)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.household_inventory(self.household, self.milk)
        self.user_inventory(self.bob, self.milk)        # another owner is fine

    def test_exchange_rate_cleanup_keeps_the_rows_that_are_used(self):
        for base, target in [('BGN', 'EUR'), ('EUR', 'BGN'), ('EUR', 'EUR'), ('BGN', 'BGN'), ('USD', 'USD'),
                             ('EUR', 'USD'), ('USD', 'EUR'), ('USD', 'BGN'), ('BGN', 'USD')]:
            ExchangeRate.objects.create(base_currency=base, target_currency=target, rate=Decimal('1.1'))

        output = run('cleanup_data', '--dry-run')
        self.assertIn('would delete 5 of 9', output)
        self.assertEqual(ExchangeRate.objects.count(), 9)                       # dry run changes nothing

        run('cleanup_data')
        left = set(ExchangeRate.objects.values_list('base_currency', 'target_currency'))
        self.assertEqual(left, {('EUR', 'USD'), ('USD', 'EUR'), ('USD', 'BGN'), ('BGN', 'USD')})
        self.assertIn('Nothing to clean up', run('cleanup_data'))             # idempotent

    def test_conversion_is_the_same_before_and_after_the_rate_cleanup(self):
        from datetime import date

        from hrp.testing import make_purchase
        from reports.utils import db_to_df
        from shopping.models import ShoppingProduct
        ExchangeRate.objects.create(base_currency='BGN', target_currency='EUR', rate=Decimal('0.5'))     # ignored
        ExchangeRate.objects.create(base_currency='EUR', target_currency='USD', rate=Decimal('1.25'))
        make_purchase(self.alice, self.milk, price=100, currency='BGN', on_date=date.today())
        make_purchase(self.alice, self.soap, price=100, currency='USD', on_date=date.today())
        before = db_to_df(ShoppingProduct.objects.all(), 'EUR')['converted_amount'].tolist()
        run('cleanup_data')
        after = db_to_df(ShoppingProduct.objects.all(), 'EUR')['converted_amount'].tolist()
        self.assertEqual(before, after)
        self.assertEqual(sorted(after), [51.13, 80.0])


class MergeDuplicatesTests(TransactionTestCase):
    """The merge itself. The unique constraints are dropped for the test so that duplicates can exist,
    exactly as in a database from before Phase 7."""

    CONSTRAINTS = [(HouseholdInventoryProduct, 'one_inventory_row_per_household_product'),
                   (InventoryProduct, 'one_inventory_row_per_user_product')]

    def setUp(self):
        from shopping.models import Product, ProductCategory
        from users.models import CustomUser, HouseHold
        with connection.schema_editor() as editor:
            for model, name in self.CONSTRAINTS:
                constraint = next(c for c in model._meta.constraints if c.name == name)
                editor.remove_constraint(model, constraint)
        self.carol = CustomUser.objects.create_user(email='carol@example.com', password='x', first_name='Carol',
                                                    last_name='User')
        self.household = HouseHold.objects.create(name='home', nickname='home', address='x', owner=self.carol)
        self.old_category = ProductCategory.objects.create(name='Стара')
        self.new_category = ProductCategory.objects.create(name='Нова')
        self.seeds = Product.objects.create(name='Семена', category=self.new_category)
        self.other = Product.objects.create(name='Друг', category=self.new_category)

    def tearDown(self):
        HouseholdInventoryProduct.objects.all().delete()
        InventoryProduct.objects.all().delete()
        with connection.schema_editor() as editor:
            for model, name in self.CONSTRAINTS:
                constraint = next(c for c in model._meta.constraints if c.name == name)
                editor.add_constraint(model, constraint)

    def row(self, product, category, quantity, amount, **extra):
        return HouseholdInventoryProduct.objects.create(
            household=self.household, product=product, category=category, quantity=Decimal(quantity),
            amount=Decimal(amount), **extra)

    def test_dry_run_reports_and_real_run_merges_into_the_oldest_row(self):
        first = self.row(self.seeds, self.old_category, '1.000', '2.00', minimum_quantity=Decimal('1'))
        second = self.row(self.seeds, self.new_category, '0.540', '1.24', daily_consumption=Decimal('0.1'))
        untouched = self.row(self.other, self.new_category, '3', '9')
        basket = HouseholdInflationBasket.objects.create(household=self.household, name='Кошница')
        HouseholdInflationBasketItem.objects.create(basket=basket, product=first)
        HouseholdInflationBasketItem.objects.create(basket=basket, product=second)      # points to the duplicate
        other_basket = HouseholdInflationBasket.objects.create(household=self.household, name='Втора')
        HouseholdInflationBasketItem.objects.create(basket=other_basket, product=second)

        output = run('cleanup_data', '--dry-run')
        self.assertIn('would merge', output)
        self.assertIn('Семена', output)
        self.assertEqual(HouseholdInventoryProduct.objects.count(), 3)
        self.assertEqual(HouseholdInflationBasketItem.objects.filter(product=second).count(), 2)

        output = run('cleanup_data')
        self.assertIn('1 duplicate group(s) merged', output)
        self.assertFalse(HouseholdInventoryProduct.objects.filter(pk=second.pk).exists())
        first.refresh_from_db()
        self.assertEqual((first.quantity, first.amount, first.average_price), (Decimal('1.540'), Decimal('3.24'), Decimal('2.10')))
        self.assertEqual((first.minimum_quantity, first.daily_consumption, first.category), (Decimal('1'), Decimal('0.10'), self.new_category))
        untouched.refresh_from_db()
        self.assertEqual(untouched.quantity, Decimal('3'))
        # basket items follow the kept row, one entry per basket
        self.assertEqual(sorted(HouseholdInflationBasketItem.objects.values_list('basket__name', 'product_id')),
                         [('Втора', first.pk), ('Кошница', first.pk)])

        self.assertIn('Nothing to clean up', run('cleanup_data'))             # idempotent
        self.assertEqual(merge_duplicates(HouseholdInventoryProduct, 'household'), [])


@skipUnless(find_binary('mysqldump') and find_binary('mysql'), 'MySQL client programs are not installed')
class FinanceRemovalTests(TransactionTestCase):
    """dump -> verify -> drop, against stand-in finance tables in the test database."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.dump = str(Path(self.folder.name) / 'finance.sql')
        self.scratch = connection.settings_dict['NAME'] + '_scratch'
        with connection.cursor() as cursor:
            cursor.execute('CREATE TABLE finance_demo (id INT PRIMARY KEY, name VARCHAR(20))')
            cursor.execute('CREATE TABLE finance_other (id INT PRIMARY KEY, demo_id INT, '
                           'FOREIGN KEY (demo_id) REFERENCES finance_demo (id))')
            cursor.execute("INSERT INTO finance_demo VALUES (1, 'а'), (2, 'б'), (3, 'в')")
            cursor.execute('INSERT INTO finance_other VALUES (1, 1), (2, 3)')
            cursor.execute("INSERT INTO django_migrations (app, name, applied) VALUES ('finance', '0001_initial', NOW())")
        from django.contrib.contenttypes.models import ContentType
        ContentType.objects.create(app_label='finance', model='demo')

    def tearDown(self):
        with connection.cursor() as cursor:
            cursor.execute('SET FOREIGN_KEY_CHECKS = 0')
            cursor.execute('DROP TABLE IF EXISTS finance_other, finance_demo')
            cursor.execute('SET FOREIGN_KEY_CHECKS = 1')
            cursor.execute(f'DROP DATABASE IF EXISTS `{self.scratch}`')
            cursor.execute("DELETE FROM django_migrations WHERE app = 'finance'")
        self.folder.cleanup()

    def state(self):
        from django.contrib.contenttypes.models import ContentType
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM django_migrations WHERE app = 'finance'")
            migrations = cursor.fetchone()[0]
        return finance_tables(), migrations, ContentType.objects.filter(app_label='finance').count()

    def test_drop_is_refused_without_a_complete_and_current_dump(self):
        with self.assertRaisesMessage(CommandError, 'does not exist'):
            run('drop_finance_tables', '--dump-file', self.dump)

        Path(self.dump).write_text('-- broken dump\nCREATE TABLE `finance_demo` (\n', encoding='utf-8')
        with self.assertRaisesMessage(CommandError, 'cut short'):
            run('drop_finance_tables', '--dump-file', self.dump)

        run('dump_finance_tables', '--output', self.dump)
        with connection.cursor() as cursor:                         # data changes after the dump was made
            cursor.execute("INSERT INTO finance_demo VALUES (4, 'г')")
        with self.assertRaisesMessage(CommandError, 'changed since the dump'):
            run('drop_finance_tables', '--dump-file', self.dump)

        Path(self.dump + '.counts.json').unlink()
        with self.assertRaisesMessage(CommandError, 'counts.json'):
            run('drop_finance_tables', '--dump-file', self.dump)
        self.assertEqual(self.state(), (['finance_demo', 'finance_other'], 1, 1))     # nothing was touched

    def test_dump_verify_then_drop(self):
        output = run('dump_finance_tables', '--output', self.dump)
        self.assertIn('Dumped 2 tables, 5 rows', output)

        with self.assertRaisesMessage(CommandError, 'scratch database'):
            run('verify_finance_dump', '--dump-file', self.dump, '--database', connection.settings_dict['NAME'])
        output = run('verify_finance_dump', '--dump-file', self.dump, '--database', self.scratch,
                     '--create-database', '--drop-database-after')
        self.assertIn('restores correctly: 2 tables, 5 rows', output)

        output = run('drop_finance_tables', '--dump-file', self.dump, '--dry-run')
        self.assertIn('would drop 2 tables', output)
        self.assertEqual(self.state(), (['finance_demo', 'finance_other'], 1, 1))

        output = run('drop_finance_tables', '--dump-file', self.dump)
        self.assertIn('removed', output)
        self.assertEqual(self.state(), ([], 0, 0))

        self.assertIn('Nothing to do', run('drop_finance_tables', '--dump-file', self.dump))          # idempotent
        self.assertIn('nothing to dump', run('dump_finance_tables', '--output', self.dump))
