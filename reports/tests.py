"""Phase 0 safety net for reports: currency conversion and per-user / per-household data isolation.

Tests marked @known_bug describe the correct behaviour for a bug listed in IMPROVEMENT_PLAN.md and are
expected to fail until that phase is done.
"""
import json
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.urls import reverse

from hrp.testing import HrpTestCase, known_bug, make_household, make_income, make_purchase, make_user
from shopping.models import Product, ShoppingProduct

from .models import (ExchangeRate, HouseholdInflationBasket, HouseholdInflationBasketItem, UserInflationBasket,
                     UserInflationBasketItem)
from .utils import by_category_spending, by_product_statistics, db_to_df, income_db_to_df


def make_rate(base, target, rate, on_date=None):
    obj = ExchangeRate.objects.create(base_currency=base, target_currency=target, rate=Decimal(str(rate)))
    if on_date:  # date_extracted is auto_now_add today, so a past date has to be forced
        ExchangeRate.objects.filter(pk=obj.pk).update(date_extracted=on_date)
    return obj


# ------------------------------------------------------------------------------------------------
# Currency conversion
# ------------------------------------------------------------------------------------------------
class CurrencyConversionTests(HrpTestCase):
    """How purchases/incomes are converted today (db_to_df / income_db_to_df)."""

    def converted_total(self, currency):
        return round(float(db_to_df(ShoppingProduct.objects.all(), currency)['converted_amount'].sum()), 2)

    def test_same_currency_is_not_converted(self):
        make_purchase(self.alice, self.milk, price='12.34', quantity=2, currency='EUR')
        self.assertEqual(self.converted_total('EUR'), 24.68)

    def test_direct_rate_is_applied_to_amount_and_price(self):
        make_rate('USD', 'EUR', '0.9')
        make_purchase(self.alice, self.milk, price=10, quantity=3, currency='USD')
        df = db_to_df(ShoppingProduct.objects.all(), 'EUR')
        self.assertEqual(df['converted_amount'].iloc[0], 27.0)
        self.assertEqual(df['converted_price'].iloc[0], 9.0)

    def test_latest_rate_wins(self):
        make_rate('USD', 'EUR', '0.5', on_date=date.today() - timedelta(days=30))
        make_rate('USD', 'EUR', '0.9')
        make_purchase(self.alice, self.milk, price=100, currency='USD')
        self.assertEqual(self.converted_total('EUR'), 90.0)

    def test_mixed_currencies_are_summed_in_target_currency(self):
        make_rate('BGN', 'EUR', '0.51129')
        make_purchase(self.alice, self.milk, price=100, currency='BGN')
        make_purchase(self.alice, self.soap, price=10, currency='EUR')
        self.assertEqual(self.converted_total('EUR'), 61.13)

    def test_discount_is_subtracted_before_conversion(self):
        item = make_purchase(self.alice, self.milk, price=10, quantity=2, currency='EUR')
        item.discount = Decimal('3')
        item.save()
        self.assertEqual(self.converted_total('EUR'), 17.0)

    def test_income_direct_rate(self):
        make_rate('USD', 'EUR', '0.9')
        make_income(self.alice, 1000, currency='USD')
        df = income_db_to_df(self.alice.incomes.all(), 'EUR')
        self.assertEqual(round(float(df['total'].sum()), 2), 900.0)

    # -- bugs to be fixed in Phase 2 ---------------------------------------------------------------
    @known_bug('Phase 2 #2: a missing rate is silently treated as 1.0')
    def test_missing_rate_is_never_counted_one_to_one(self):
        make_purchase(self.alice, self.milk, price=100, currency='USD')
        try:
            total = self.converted_total('EUR')
        except Exception:
            return  # refusing to convert is fine; inventing a rate is not
        self.assertNotEqual(total, 100.0)

    @known_bug('Phase 2 #2: income with a missing rate is silently counted 1:1')
    def test_income_missing_rate_is_never_counted_one_to_one(self):
        make_income(self.alice, 1000, currency='USD')
        try:
            total = round(float(income_db_to_df(self.alice.incomes.all(), 'EUR')['total'].sum()), 2)
        except Exception:
            return
        self.assertNotEqual(total, 1000.0)

    @known_bug('Phase 2 #5: BGN<->EUR must use the fixed peg 1.95583 and need no stored rate')
    def test_bgn_eur_uses_fixed_peg_without_stored_rate(self):
        make_purchase(self.alice, self.milk, price='195.583', currency='BGN')  # stored as 195.58
        self.assertEqual(self.converted_total('EUR'), 100.0)

    @known_bug('Phase 2 #2: no inverse lookup (only EUR->USD stored, USD->EUR needed)')
    def test_inverse_rate_is_used(self):
        make_rate('EUR', 'USD', '1.25')
        make_purchase(self.alice, self.milk, price=100, currency='USD')
        self.assertEqual(self.converted_total('EUR'), 80.0)

    @known_bug('Phase 2 #2: no cross rate via EUR (USD->BGN from USD->EUR and the peg)')
    def test_cross_rate_via_eur(self):
        make_rate('USD', 'EUR', '0.5')
        make_purchase(self.alice, self.milk, price=100, currency='USD')
        self.assertEqual(self.converted_total('BGN'), 97.79)

    @known_bug('Phase 2 #3: ExchangeRate.date_extracted is auto_now_add, the given date is ignored')
    def test_exchange_rate_keeps_the_given_date(self):
        past = date(2025, 3, 14)
        rate = ExchangeRate.objects.create(base_currency='USD', target_currency='EUR', rate=Decimal('0.9'),
                                           date_extracted=past)
        rate.refresh_from_db()
        self.assertEqual(rate.date_extracted, past)

    @known_bug('Phase 2 #6: lowest/highest price are picked by the unconverted price')
    def test_highest_and_lowest_price_compare_converted_prices(self):
        make_rate('BGN', 'EUR', '0.51129')
        make_purchase(self.alice, self.milk, price=10, currency='BGN')   # 5.11 EUR
        make_purchase(self.alice, self.soap, price=6, currency='EUR')    # 6.00 EUR
        df = db_to_df(ShoppingProduct.objects.all(), 'EUR')
        _, lowest, highest = by_product_statistics(df)
        self.assertEqual(highest['product__name'], 'Сапун')
        self.assertEqual(lowest['product__name'], 'Мляко')

    @known_bug('Phase 2 #7: products without category disappear from the category totals')
    def test_uncategorised_products_stay_in_category_totals(self):
        loose = Product.objects.create(name='Без категория продукт')
        make_purchase(self.alice, self.milk, price=10)
        make_purchase(self.alice, loose, price=5)
        df = db_to_df(ShoppingProduct.objects.all(), 'EUR')
        main, sub = by_category_spending(df)
        self.assertEqual(round(sum(row['y'] for row in main), 2), 15.0)
        self.assertEqual(round(sum(row['y'] for row in sub), 2), 15.0)

    @known_bug('Phase 2/7: db_to_df crashes on an empty queryset (new user -> 500 on several pages)')
    def test_empty_queryset_gives_empty_frame(self):
        df = db_to_df(ShoppingProduct.objects.none(), 'EUR')
        self.assertTrue(df.empty)


class CurrencyModuleSpecTests(HrpTestCase):
    """Contract of the new reports/currency.py (Phase 2). Fails until the module exists."""

    @known_bug('Phase 2: reports/currency.py does not exist yet')
    def test_get_rate_contract(self):
        from reports.currency import BGN_PER_EUR, MissingRate, get_rate

        self.assertEqual(BGN_PER_EUR, Decimal('1.95583'))
        self.assertEqual(get_rate('EUR', 'EUR'), 1)
        self.assertEqual(Decimal(get_rate('EUR', 'BGN')), BGN_PER_EUR)
        self.assertAlmostEqual(float(get_rate('BGN', 'EUR')), 1 / 1.95583, places=9)
        with self.assertRaises(MissingRate):
            get_rate('USD', 'EUR')

        make_rate('USD', 'EUR', '0.8', on_date=date(2025, 1, 10))
        make_rate('USD', 'EUR', '0.9', on_date=date(2025, 6, 10))
        self.assertAlmostEqual(float(get_rate('USD', 'EUR')), 0.9)                              # latest
        self.assertAlmostEqual(float(get_rate('USD', 'EUR', on_date=date(2025, 3, 1))), 0.8)    # on or before
        self.assertAlmostEqual(float(get_rate('EUR', 'USD')), 1 / 0.9)                          # inverse
        self.assertAlmostEqual(float(get_rate('USD', 'BGN')), 0.9 * 1.95583)                    # cross via EUR


# ------------------------------------------------------------------------------------------------
# Data isolation: every report shows only the user's (or their household's) data
# ------------------------------------------------------------------------------------------------
class ReportIsolationTests(HrpTestCase):
    """alice spends 15, bob 100, the household (carol + dave) 3000 — all EUR, all in the current month."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.day = date.today().replace(day=1)
        cls.month = cls.day.strftime('%Y-%m')
        make_purchase(cls.alice, cls.milk, price=10, on_date=cls.day)
        make_purchase(cls.alice, cls.soap, price=5, on_date=cls.day)
        make_purchase(cls.bob, cls.milk, price=100, on_date=cls.day)
        make_purchase(cls.carol, cls.milk, price=1000, on_date=cls.day)
        make_purchase(cls.dave, cls.soap, price=2000, on_date=cls.day)
        make_income(cls.alice, 111, on_date=cls.day)
        make_income(cls.bob, 222, on_date=cls.day)
        make_income(cls.carol, 3000, on_date=cls.day)
        make_income(cls.dave, 4000, on_date=cls.day)
        cls.expected_spent = {cls.alice: 15.0, cls.bob: 100.0, cls.carol: 3000.0, cls.dave: 3000.0}
        cls.expected_income = {cls.alice: 111.0, cls.bob: 222.0, cls.carol: 7000.0, cls.dave: 7000.0}

    def get_as(self, user, url_name, params=None, **kwargs):
        self.client.force_login(user)
        response = self.client.get(reverse(url_name, kwargs=kwargs), params or {})
        self.assertEqual(response.status_code, 200)
        return response

    # -- login required ----------------------------------------------------------------------------
    def test_login_required_on_protected_reports(self):
        for name in ['reports_home', 'spendings_history', 'by_shop', 'create_inflation_basket', 'income_analysis',
                     'consumption_summary']:
            with self.subTest(view=name):
                self.assertLoginRequired(reverse(name))
        self.assertLoginRequired(reverse('edit_inflation_basket', kwargs={'basket_id': 1}))

    def test_login_required_price_changes(self):
        self.assertLoginRequired(reverse('price_changes'))

    def test_login_required_save_inflation_basket(self):
        self.assertLoginRequired(reverse('save_inflation_basket'), method='post', data={'name': 'x'})

    def test_login_required_income_vs_spendings(self):
        self.assertLoginRequired(reverse('income_spendings_comparison'))

    def test_login_required_by_category_table(self):
        self.assertLoginRequired(reverse('by_category_table'), data={'month': self.month, 'currency': 'EUR'})

    # -- totals per user ---------------------------------------------------------------------------
    def test_spendings_history_shows_only_own_or_household_spending(self):
        for user, expected in self.expected_spent.items():
            with self.subTest(user=user.email):
                response = self.get_as(user, 'spendings_history', {'currency': 'EUR'})
                self.assertEqual(float(response.context['total_spent']), expected)

    def test_by_shop_shows_only_own_or_household_spending(self):
        for user, expected in self.expected_spent.items():
            with self.subTest(user=user.email):
                response = self.get_as(user, 'by_shop', {'currency': 'EUR'})
                self.assertEqual(round(float(response.context['total_for_selection']), 2), expected)

    def test_consumption_summary_shows_only_own_or_household_spending(self):
        for user, expected in self.expected_spent.items():
            with self.subTest(user=user.email):
                response = self.get_as(user, 'consumption_summary', {'currency': 'EUR', 'fast': '12'})
                self.assertEqual(round(float(response.context['total_spent']), 2), expected)

    def test_income_analysis_shows_only_own_or_household_income(self):
        for user, expected in self.expected_income.items():
            with self.subTest(user=user.email):
                response = self.get_as(user, 'income_analysis', {'currency': 'EUR'})
                self.assertEqual(float(response.context['total_income']), expected)

    def test_income_vs_spendings_shows_only_own_or_household_data(self):
        for user in self.expected_spent:
            with self.subTest(user=user.email):
                response = self.get_as(user, 'income_spendings_comparison', {'currency': 'EUR'})
                income = sum(json.loads(response.context['income_series'])[0]['data'])
                spent = sum(json.loads(response.context['spendings_series'])[0]['data'])
                self.assertEqual(income, self.expected_income[user])
                self.assertEqual(spent, self.expected_spent[user])

    def test_by_category_table_shows_only_own_or_household_spending(self):
        for user, expected in self.expected_spent.items():
            with self.subTest(user=user.email):
                response = self.get_as(user, 'by_category_table', {'month': self.month, 'currency': 'EUR'})
                self.assertEqual(round(float(response.context['total_current']), 2), expected)

    def test_price_history_product_picker_lists_only_own_products(self):
        only_bob = Product.objects.create(name='Само на Боб', category=self.cat_dairy)
        make_purchase(self.bob, only_bob, price=1, on_date=self.day)
        # no baskets exist, so the (unscoped) basket loop in price_changes is not reached
        response = self.get_as(self.alice, 'price_changes')
        names = [p.name for p in response.context['products']]
        self.assertEqual(sorted(names), ['Мляко', 'Сапун'])

    # -- inflation baskets -------------------------------------------------------------------------
    def make_user_basket(self, user, name, product):
        basket = UserInflationBasket.objects.create(user=user, name=name)
        UserInflationBasketItem.objects.create(basket=basket, product=self.user_inventory(user, product))
        return basket

    def test_price_changes_shows_only_own_baskets(self):
        self.make_user_basket(self.alice, 'Кошница на Алис', self.milk)
        self.make_user_basket(self.bob, 'Кошница на Боб', self.milk)
        response = self.get_as(self.alice, 'price_changes')
        self.assertEqual([b.name for b in response.context['inflation_baskets']], ['Кошница на Алис'])

    def test_price_changes_shows_only_own_household_baskets(self):
        other_home = HouseholdInflationBasket.objects.create(household=self.household, name='Домашна кошница')
        HouseholdInflationBasketItem.objects.create(
            basket=other_home, product=self.household_inventory(self.household, self.milk))
        erin = make_user('erin@example.com', 'Erin')
        erin_home = make_household(erin, 'erin_home')
        make_purchase(erin, self.milk, price=3, on_date=self.day)
        foreign = HouseholdInflationBasket.objects.create(household=erin_home, name='Чужда домашна кошница')
        HouseholdInflationBasketItem.objects.create(
            basket=foreign, product=self.household_inventory(erin_home, self.milk))
        response = self.get_as(self.carol, 'price_changes')
        self.assertEqual([b.name for b in response.context['inflation_baskets']], ['Домашна кошница'])

    def test_create_basket_lists_only_own_inventory(self):
        mine = self.user_inventory(self.alice, self.milk)
        self.user_inventory(self.bob, self.soap)
        response = self.get_as(self.alice, 'create_inflation_basket')
        self.assertEqual([p.pk for p in response.context['products']], [mine.pk])

    def test_edit_basket_lists_only_own_inventory(self):
        basket = self.make_user_basket(self.alice, 'Кошница на Алис', self.milk)
        self.user_inventory(self.bob, self.soap)
        response = self.get_as(self.alice, 'edit_inflation_basket', basket_id=basket.pk)
        self.assertEqual([p.product.name for p in response.context['products']], ['Мляко'])

    def test_save_basket_rejects_foreign_inventory_products(self):
        foreign = self.user_inventory(self.bob, self.soap)
        self.client.force_login(self.alice)
        self.client.post(reverse('save_inflation_basket'), {'name': 'Чужда', 'product_id[]': [foreign.pk]})
        self.assertFalse(UserInflationBasketItem.objects.filter(product=foreign).exists())

    def test_edit_foreign_basket_is_404(self):
        basket = self.make_user_basket(self.bob, 'Кошница на Боб', self.milk)
        self.client.force_login(self.alice)
        response = self.client.get(reverse('edit_inflation_basket', kwargs={'basket_id': basket.pk}))
        self.assertEqual(response.status_code, 404)

    def test_edit_foreign_basket_does_not_change_it(self):
        basket = self.make_user_basket(self.bob, 'Кошница на Боб', self.milk)
        self.client.force_login(self.alice)
        try:
            self.client.post(reverse('edit_inflation_basket', kwargs={'basket_id': basket.pk}), {'name': 'Хак'})
        except UserInflationBasket.DoesNotExist:
            pass  # today: unhandled DoesNotExist; Phase 1 turns it into a 404
        basket.refresh_from_db()
        self.assertEqual(basket.name, 'Кошница на Боб')
        self.assertEqual(basket.user_basket_items.count(), 1)

    def test_two_users_can_use_the_same_basket_name(self):
        UserInflationBasket.objects.create(user=self.alice, name='Храна')
        with transaction.atomic():
            UserInflationBasket.objects.create(user=self.bob, name='Храна')
        self.assertEqual(UserInflationBasket.objects.filter(name='Храна').count(), 2)
