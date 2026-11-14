"""Phase 0 safety net for reports: currency conversion and per-user / per-household data isolation.

(The @known_bug marker in hrp/testing.py is for tests that describe a bug that is not fixed yet; none are left.)
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.urls import reverse

from hrp.testing import HrpTestCase, known_bug, make_household, make_income, make_purchase, make_user
from shopping.models import Product, ShoppingProduct

from .models import (ExchangeRate, HouseholdInflationBasket, HouseholdInflationBasketItem, UserInflationBasket,
                     UserInflationBasketItem)
from .currency import clear_cache
from . import services
from .filters import ReportFilters
from .utils import db_to_df, income_db_to_df, rate_warnings


def make_rate(base, target, rate, on_date=None):
    obj = ExchangeRate.objects.create(base_currency=base, target_currency=target, rate=Decimal(str(rate)))
    if on_date:
        obj.date_extracted = on_date
        obj.save()
    return obj


# ------------------------------------------------------------------------------------------------
# Currency conversion
# ------------------------------------------------------------------------------------------------
class CurrencyConversionTests(HrpTestCase):
    """How purchases/incomes are converted (db_to_df / income_db_to_df on top of reports/currency.py)."""

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

    def test_rate_of_the_purchase_date_is_used(self):
        """A purchase keeps the rate of its own day: later rate changes do not move old totals."""
        make_rate('USD', 'EUR', '0.80', on_date=date(2025, 1, 10))
        make_rate('USD', 'EUR', '0.90', on_date=date(2025, 6, 10))
        make_purchase(self.alice, self.milk, price=100, currency='USD', on_date=date(2025, 1, 10))   # 80
        make_purchase(self.alice, self.milk, price=100, currency='USD', on_date=date(2025, 3, 1))    # 80 (on or before)
        make_purchase(self.alice, self.milk, price=100, currency='USD', on_date=date(2025, 6, 10))   # 90
        make_purchase(self.alice, self.milk, price=100, currency='USD', on_date=date(2025, 12, 1))   # 90
        df = db_to_df(ShoppingProduct.objects.all(), 'EUR')
        self.assertEqual(df['converted_amount'].tolist(), [80.0, 80.0, 90.0, 90.0])
        self.assertEqual(rate_warnings(df), [])

    def test_purchase_older_than_the_first_rate_uses_it_and_warns(self):
        make_rate('USD', 'EUR', '0.90', on_date=date(2025, 6, 10))
        make_purchase(self.alice, self.milk, price=100, currency='USD', on_date=date(2025, 1, 1))
        df = db_to_df(ShoppingProduct.objects.all(), 'EUR')
        self.assertEqual(self.converted_total('EUR'), 90.0)
        self.assertEqual(len(rate_warnings(df)), 1)
        self.assertIn('USD', rate_warnings(df)[0])

    def test_missing_rate_rows_are_left_out_and_reported(self):
        make_purchase(self.alice, self.milk, price=100, currency='USD')
        make_purchase(self.alice, self.soap, price=10, currency='EUR')
        df = db_to_df(ShoppingProduct.objects.all(), 'EUR')
        self.assertEqual(round(float(df['converted_amount'].sum()), 2), 10.0)
        self.assertEqual(len(rate_warnings(df)), 1)
        self.assertIn('USD', rate_warnings(df)[0])

    def test_conversion_runs_no_query_per_row(self):
        make_rate('USD', 'EUR', '0.9')
        for day in range(1, 21):
            make_purchase(self.alice, self.milk, price=day, currency='USD', on_date=date(2026, 1, day))
            make_purchase(self.alice, self.soap, price=day, currency='BGN', on_date=date(2026, 1, day))
        clear_cache()
        with self.assertNumQueries(2):          # the purchases + all exchange rates
            db_to_df(ShoppingProduct.objects.all(), 'EUR')
        with self.assertNumQueries(1):          # rates are already in memory
            db_to_df(ShoppingProduct.objects.all(), 'BGN')

    def test_unknown_currency_falls_back_to_eur(self):
        make_purchase(self.alice, self.milk, price='195.583', currency='BGN')
        for value in ['', None, 'XXX']:
            with self.subTest(value=value):
                self.assertEqual(self.converted_total(value), 100.0)

    def test_change_calculator_uses_the_same_rates(self):
        from fastapps.change_calculator.services import convert
        self.assertEqual(convert(10, 'EUR', 'BGN'), Decimal('19.5583'))
        with self.assertRaises(ValueError):
            convert(10, 'USD', 'BGN')

    def test_missing_rate_is_never_counted_one_to_one(self):
        make_purchase(self.alice, self.milk, price=100, currency='USD')
        try:
            total = self.converted_total('EUR')
        except Exception:
            return  # refusing to convert is fine; inventing a rate is not
        self.assertNotEqual(total, 100.0)

    def test_income_missing_rate_is_never_counted_one_to_one(self):
        make_income(self.alice, 1000, currency='USD')
        try:
            total = round(float(income_db_to_df(self.alice.incomes.all(), 'EUR')['total'].sum()), 2)
        except Exception:
            return
        self.assertNotEqual(total, 1000.0)

    def test_bgn_eur_uses_fixed_peg_without_stored_rate(self):
        make_purchase(self.alice, self.milk, price='195.583', currency='BGN')  # stored as 195.58
        self.assertEqual(self.converted_total('EUR'), 100.0)

    def test_inverse_rate_is_used(self):
        make_rate('EUR', 'USD', '1.25')
        make_purchase(self.alice, self.milk, price=100, currency='USD')
        self.assertEqual(self.converted_total('EUR'), 80.0)

    def test_cross_rate_via_eur(self):
        make_rate('USD', 'EUR', '0.5')
        make_purchase(self.alice, self.milk, price=100, currency='USD')
        self.assertEqual(self.converted_total('BGN'), 97.79)

    def test_exchange_rate_keeps_the_given_date(self):
        past = date(2025, 3, 14)
        rate = ExchangeRate.objects.create(base_currency='USD', target_currency='EUR', rate=Decimal('0.9'),
                                           date_extracted=past)
        rate.refresh_from_db()
        self.assertEqual(rate.date_extracted, past)

    def test_uncategorised_products_stay_in_category_totals(self):
        loose = Product.objects.create(name='Без категория продукт')
        make_purchase(self.alice, self.milk, price=10)
        make_purchase(self.alice, loose, price=5)
        data = services.categories(self.alice, ReportFilters({}))
        self.assertEqual(data['spent'], 15.0)
        self.assertEqual(round(sum(row['value'] for row in data['bars']), 2), 15.0)
        self.assertEqual(round(sum(row['current'] for row in data['yoy_table'].rows), 2), 15.0)
        self.assertIn('Без категория', [row['name'] for row in data['bars']])

    def test_empty_queryset_gives_empty_frame(self):
        df = db_to_df(ShoppingProduct.objects.none(), 'EUR')
        self.assertTrue(df.empty)


class CurrencyModuleSpecTests(HrpTestCase):
    """Contract of reports/currency.py."""

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


class RateCommandTests(HrpTestCase):
    """fetch_rates / audit_rates management commands (the HTTP call is replaced)."""

    def test_fetch_rates_stores_eur_rates_for_the_given_date(self):
        from io import StringIO
        from unittest import mock

        from django.core.management import call_command
        with mock.patch('reports.rates._from_frankfurter', return_value={'USD': Decimal('1.25')}) as source:
            call_command('fetch_rates', '--date', '2026-10-28', stdout=StringIO())
            call_command('fetch_rates', '--date', '2026-10-28', stdout=StringIO())      # twice: no duplicate
        self.assertEqual(source.call_args[0][0], date(2026, 10, 28))
        rate = ExchangeRate.objects.get()
        self.assertEqual((rate.base_currency, rate.target_currency, rate.date_extracted, rate.rate),
                         ('EUR', 'USD', date(2026, 10, 28), Decimal('1.25')))
        make_purchase(self.alice, self.milk, price=100, currency='USD', on_date=date(2026, 10, 29))
        self.assertEqual(round(float(db_to_df(ShoppingProduct.objects.all(), 'EUR')['total'].sum()), 2), 80.0)

    def test_fetch_failure_is_reported_and_stores_nothing(self):
        from io import StringIO
        from unittest import mock

        from django.core.management import CommandError, call_command
        with mock.patch.dict('os.environ', {'API_EXCHANGE_RATES': ''}):
            with self.assertRaises(CommandError):       # network is blocked in tests
                call_command('fetch_rates', stdout=StringIO(), stderr=StringIO())
        self.assertFalse(ExchangeRate.objects.exists())

    def test_audit_rates_lists_records_without_a_usable_rate(self):
        from io import StringIO

        from django.core.management import call_command
        from .rates import audit
        make_purchase(self.alice, self.milk, price=1, currency='BGN', on_date=date(2025, 1, 1))     # peg: fine
        make_purchase(self.alice, self.milk, price=1, currency='USD', on_date=date(2025, 1, 1))
        self.assertEqual([p[0] for p in audit()], ['missing'])
        make_rate('EUR', 'USD', '1.1', on_date=date(2025, 3, 1))
        self.assertEqual([p[0] for p in audit()], ['later'])
        make_rate('EUR', 'USD', '1.1', on_date=date(2024, 12, 1))
        self.assertEqual([p[0] for p in audit()], ['stale'])
        make_rate('EUR', 'USD', '1.1', on_date=date(2024, 12, 31))
        self.assertEqual(audit(), [])
        out = StringIO()
        call_command('audit_rates', stdout=out)
        self.assertIn('Every record has an exchange rate', out.getvalue())


class ReportFiltersTests(HrpTestCase):
    """The shared filter bar: presets, comparison periods, bad input, links."""
    today = date(2026, 3, 31)

    def make(self, **params):
        return ReportFilters(params, today=self.today)

    def test_presets(self):
        expected = {
            'this_month': (date(2026, 3, 1), date(2026, 3, 31)),
            'last_month': (date(2026, 2, 1), date(2026, 2, 28)),
            '3m': (date(2026, 1, 1), date(2026, 3, 31)),
            '12m': (date(2025, 4, 1), date(2026, 3, 31)),
            'ytd': (date(2026, 1, 1), date(2026, 3, 31)),
        }
        for period, (start, end) in expected.items():
            with self.subTest(period=period):
                filters = self.make(period=period)
                self.assertEqual((filters.start, filters.end), (start, end))

    def test_custom_period_and_comparison_periods(self):
        filters = self.make(period='custom', **{'from': '2024-02-29', 'to': '2024-03-10'})
        self.assertEqual((filters.start, filters.end, filters.days), (date(2024, 2, 29), date(2024, 3, 10), 11))
        self.assertEqual(filters.previous, (date(2024, 2, 18), date(2024, 2, 28)))
        self.assertEqual(filters.last_year, (date(2023, 2, 28), date(2023, 3, 10)))     # 29 February is safe
        self.assertEqual(self.make(period='last_month').previous, (date(2026, 1, 1), date(2026, 1, 28)))

    def test_bad_input_falls_back_to_defaults(self):
        for params in [{'period': 'nonsense'}, {'period': 'custom', 'from': 'x', 'to': '2026-01-01'},
                       {'period': 'custom', 'from': '2026-02-01', 'to': '2026-01-01'},
                       {'currency': 'XXX', 'scope': 'everyone'}]:
            with self.subTest(params=params):
                filters = self.make(**params)
                self.assertEqual((filters.period, filters.currency, filters.scope), ('this_month', 'EUR', 'all'))

    def test_links_keep_the_filters_and_leave_defaults_out(self):
        self.assertEqual(self.make().query(), '')
        filters = self.make(period='6m', currency='BGN', scope='mine')
        self.assertEqual(filters.query(), '?period=6m&currency=BGN&scope=mine')
        self.assertEqual(filters.query(main=3), '?period=6m&currency=BGN&scope=mine&main=3')
        custom = self.make(period='custom', **{'from': '2026-01-05', 'to': '2026-01-20'})
        self.assertEqual(custom.query(), '?period=custom&from=2026-01-05&to=2026-01-20')
        self.assertEqual(custom.query(period='3m'), '?period=3m')


class BasketIndexTests(HrpTestCase):
    """Personal inflation is a price index (fixed basket), not the amount spent."""

    def index(self):
        filters = ReportFilters({'period': 'custom', 'from': '2026-01-01', 'to': '2026-12-31'})
        frame = services.load_spending(self.alice, filters, filters.start, filters.end)
        return services.basket_index(frame)

    def test_buying_more_at_the_same_price_is_not_inflation(self):
        make_purchase(self.alice, self.milk, price=2, quantity=1, on_date=date(2026, 1, 10))
        make_purchase(self.alice, self.milk, price=2, quantity=10, on_date=date(2026, 2, 10))
        make_purchase(self.alice, self.milk, price=2, quantity=3, on_date=date(2026, 3, 10))
        result = self.index()
        self.assertEqual(result['values'], [100.0, 100.0, 100.0])
        self.assertEqual(result['change'], 0.0)

    def test_price_changes_move_the_index_weighted_by_quantity(self):
        # milk: 10 a month, 1.00 -> 1.50 ; soap: 1 a month, 10.00 all the time -> basket 20 -> 25 = +25 %
        for month, milk_price in [(1, '1.00'), (2, '1.00'), (3, '1.50')]:
            make_purchase(self.alice, self.milk, price=milk_price, quantity=10, on_date=date(2026, month, 5))
            make_purchase(self.alice, self.soap, price=10, quantity=1, on_date=date(2026, month, 5))
        result = self.index()
        self.assertEqual(result['values'], [100.0, 100.0, 125.0])
        self.assertEqual((result['change'], result['products']), (25.0, 2))

    def test_month_without_purchase_keeps_the_last_price_and_discounts_count(self):
        make_purchase(self.alice, self.milk, price=2, quantity=1, on_date=date(2026, 1, 10))
        item = make_purchase(self.alice, self.milk, price=4, quantity=1, on_date=date(2026, 3, 10))
        item.discount = Decimal('1')         # paid 3.00
        item.save()
        self.assertEqual(self.index()['values'], [100.0, 100.0, 150.0])

    def test_automatic_basket_skips_things_without_a_stable_unit_price(self):
        gift = Product.objects.create(name='Подарък')
        for month, gift_price in [(1, 10), (2, 300), (3, 45)]:
            make_purchase(self.alice, self.milk, price=2, on_date=date(2026, month, 5))
            make_purchase(self.alice, gift, price=gift_price, on_date=date(2026, month, 5))
        make_purchase(self.alice, self.soap, price=1, on_date=date(2026, 1, 5))          # only one month
        filters = ReportFilters({'period': 'custom', 'from': '2026-01-01', 'to': '2026-12-31'})
        frame = services.load_spending(self.alice, filters, filters.start, filters.end)
        self.assertEqual(services.regular_products(frame), {self.milk.pk})
        data = services.prices(self.alice, filters)
        self.assertEqual([(i['key'], i['products'], i['change']) for i in data['indexes']], [('regular', 1, 0.0)])
        self.assertEqual(len(data['changes_table'].rows), 2)        # the full table still lists the gift
        self.assertEqual([row['product'] for row in data['increases']], [])

    def test_one_month_of_data_gives_no_index(self):
        make_purchase(self.alice, self.milk, price=2, on_date=date(2026, 1, 10))
        self.assertIsNone(self.index())


# ------------------------------------------------------------------------------------------------
# The Reports hub: every tab shows only the user's (or their household's) data
# ------------------------------------------------------------------------------------------------
HUB_TABS = ['reports_home', 'reports_categories', 'reports_shops', 'reports_prices', 'reports_cash_flow',
            'reports_budget']
LEGACY_URLS = ['spendings_history', 'by_shop', 'price_changes', 'income_analysis', 'income_spendings_comparison',
               'consumption_summary', 'by_category_table']


class ReportHubTests(HrpTestCase):
    """alice spends 15, bob 100, the household (carol + dave) 3000 — all EUR, all in the current month."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.day = date.today().replace(day=1)
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

    def data(self, user, url_name, params=None):
        return self.get_as(user, url_name, params).context['data']

    # -- access ------------------------------------------------------------------------------------
    def test_login_required_everywhere(self):
        for name in HUB_TABS + LEGACY_URLS + ['create_inflation_basket']:
            with self.subTest(view=name):
                self.assertLoginRequired(reverse(name))
        self.assertLoginRequired(reverse('edit_inflation_basket', kwargs={'basket_id': 1}))
        self.assertLoginRequired(reverse('save_inflation_basket'), method='post', data={'name': 'x'})
        self.assertLoginRequired(reverse('reports_home') + '?export=largest_purchases&format=csv')

    def test_every_tab_opens_for_a_user_without_any_data(self):
        newcomer = make_user('new@example.com', 'New')
        for name in HUB_TABS:
            for params in ({}, {'period': '12m', 'currency': 'BGN', 'scope': 'mine'}):
                with self.subTest(view=name, params=params):
                    self.get_as(newcomer, name, params)
        self.get_as(newcomer, 'reports_categories', {'main': 999, 'sub': 999})
        self.get_as(newcomer, 'reports_prices', {'product': 999})
        self.get_as(newcomer, 'reports_shops', {'shop': ['999', 'abc']})

    def test_old_report_addresses_redirect_to_the_matching_tab(self):
        self.client.force_login(self.alice)
        cases = [
            ('spendings_history', {'date_from': '2026-01-05', 'date_to': '2026-01-20', 'currency': 'BGN',
                                   'not_for_household_filter': 'external'},
             reverse('reports_home') + '?period=custom&from=2026-01-05&to=2026-01-20&currency=BGN&scope=external'),
            ('by_category_table', {'month': '2026-02', 'currency': 'EUR'},
             reverse('reports_categories') + '?period=custom&from=2026-02-01&to=2026-02-28'),
            ('price_changes', {'product': '7', 'currency': 'EUR'}, reverse('reports_prices') + '?product=7'),
            ('by_shop', {}, reverse('reports_shops')),
            ('income_spendings_comparison', {'currency': 'nonsense'}, reverse('reports_cash_flow')),
            ('consumption_summary', {'fast': '3'}, reverse('reports_categories')),
        ]
        for name, params, target in cases:
            with self.subTest(view=name):
                response = self.client.get(reverse(name), params)
                self.assertRedirects(response, target, fetch_redirect_response=False)

    # -- totals per user ---------------------------------------------------------------------------
    def test_overview_shows_only_own_or_household_money(self):
        for user in self.expected_spent:
            with self.subTest(user=user.email):
                kpi = self.data(user, 'reports_home')['kpi']
                self.assertEqual(kpi['spent'], self.expected_spent[user])
                self.assertEqual(kpi['income'], self.expected_income[user])
                self.assertEqual(kpi['net'], round(self.expected_income[user] - self.expected_spent[user], 2))

    def test_other_tabs_show_only_own_or_household_money(self):
        for user, expected in self.expected_spent.items():
            with self.subTest(user=user.email):
                self.assertEqual(self.data(user, 'reports_categories')['spent'], expected)
                self.assertEqual(self.data(user, 'reports_shops')['spent'], expected)
                flow = self.data(user, 'reports_cash_flow')
                self.assertEqual((flow['spending'], flow['income']), (expected, self.expected_income[user]))

    def test_scope_filter(self):
        make_purchase(self.dave, self.milk, price=7, on_date=self.day, not_for_household=True)
        expected = {'all': 3007.0, 'household': 3000.0, 'external': 7.0, 'mine': 2007.0}
        for scope, spent in expected.items():
            with self.subTest(scope=scope):
                self.assertEqual(self.data(self.dave, 'reports_home', {'scope': scope})['kpi']['spent'], spent)
        self.assertEqual(self.data(self.dave, 'reports_home', {'scope': 'mine'})['kpi']['income'], 4000.0)

    def test_overview_comparisons_and_chart(self):
        from dateutil.relativedelta import relativedelta
        make_purchase(self.alice, self.milk, price=30, on_date=self.day - relativedelta(months=1))
        make_purchase(self.alice, self.milk, price=5, on_date=self.day - relativedelta(years=1))
        data = self.data(self.alice, 'reports_home')
        kpi = data['kpi']
        self.assertEqual((kpi['previous'], kpi['previous_diff'], kpi['previous_pct']), (30.0, -15.0, -50.0))
        self.assertEqual((kpi['last_year'], kpi['last_year_diff'], kpi['last_year_pct']), (5.0, 10.0, 200.0))
        self.assertEqual(kpi['purchases'], 2)
        self.assertEqual(len(data['chart']['months']), 12)
        self.assertEqual(data['chart']['spending'][-2:], [30.0, 15.0])
        self.assertEqual(data['chart']['income'][-1], 111.0)
        self.assertEqual([row['name'] for row in data['top_categories']], ['Храна', 'Дом'])
        self.assertEqual([row['amount'] for row in data['largest_table'].rows], [10.0, 5.0])

    def test_overview_query_budget(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        self.client.force_login(self.carol)
        with CaptureQueriesContext(connection) as ctx:
            self.assertEqual(self.client.get(reverse('reports_home')).status_code, 200)
        self.assertLessEqual(len(ctx), 15, f'overview ran {len(ctx)} queries')

    # -- categories --------------------------------------------------------------------------------
    def test_category_drill_down_and_year_over_year(self):
        from dateutil.relativedelta import relativedelta
        make_purchase(self.alice, self.milk, price=4, on_date=self.day - relativedelta(years=1))
        top = self.data(self.alice, 'reports_categories')
        self.assertEqual(top['level'], 'main')
        self.assertEqual([(row['name'], row['value']) for row in top['bars']], [('Храна', 10.0), ('Дом', 5.0)])
        food = next(row for row in top['yoy_table'].rows if row['name'] == 'Храна')
        self.assertEqual((food['current'], food['previous'], food['diff'], food['pct']), (10.0, 4.0, 6.0, 150.0))
        self.assertEqual(top['yoy_table'].total['current'], 15.0)

        sub = self.data(self.alice, 'reports_categories', {'main': self.main_food.pk})
        self.assertEqual((sub['level'], sub['main_name'], sub['spent']), ('sub', 'Храна', 10.0))
        self.assertEqual([row['name'] for row in sub['bars']], ['Млечни'])

        products = self.data(self.alice, 'reports_categories', {'main': self.main_food.pk, 'sub': self.cat_dairy.pk})
        self.assertEqual((products['level'], products['sub_name']), ('products', 'Млечни'))
        self.assertEqual([(row['product'], row['spent'], row['times']) for row in products['products_table'].rows],
                         [('Мляко', 10.0, 1)])

    def test_drill_down_cannot_reach_other_users_data(self):
        data = self.data(self.alice, 'reports_categories', {'main': self.main_food.pk})
        self.assertEqual(data['spent'], 10.0)       # bob and the household also bought milk

    # -- shops -------------------------------------------------------------------------------------
    def test_shop_comparison_marks_the_cheapest_shop(self):
        from shopping.models import Shop
        cheap, dear = Shop.objects.create(name='Евтин'), Shop.objects.create(name='Скъп')
        make_purchase(self.bob, self.soap, price=2, quantity=2, on_date=self.day, shop=cheap)
        make_purchase(self.bob, self.soap, price=3, quantity=2, on_date=self.day, shop=dear)
        data = self.data(self.bob, 'reports_shops')
        row = data['comparison_table'].rows[0]
        self.assertEqual((row['product'], row['Евтин'], row['Скъп'], row['highlight']), ('Сапун', 2.0, 3.0, ['Евтин']))
        self.assertEqual([shop['name'] for shop in data['shop_choices']], ['Евтин', 'Скъп', 'Тестов магазин'])
        only = self.data(self.bob, 'reports_shops', {'shop': [cheap.pk]})
        self.assertEqual((only['spent'], [r['shop'] for r in only['shop_rows']]), (4.0, ['Евтин']))

    # -- prices ------------------------------------------------------------------------------------
    def make_user_basket(self, user, name, product):
        basket = UserInflationBasket.objects.create(user=user, name=name)
        UserInflationBasketItem.objects.create(basket=basket, product=self.user_inventory(user, product))
        return basket

    def basket_names(self, user):
        return [index['name'] for index in self.data(user, 'reports_prices')['indexes'] if index['basket_id']]

    def test_prices_tab_lists_only_own_products_and_baskets(self):
        only_bob = Product.objects.create(name='Само на Боб', category=self.cat_dairy)
        make_purchase(self.bob, only_bob, price=1, on_date=self.day)
        self.make_user_basket(self.alice, 'Кошница на Алис', self.milk)
        self.make_user_basket(self.bob, 'Кошница на Боб', self.milk)
        data = self.data(self.alice, 'reports_prices')
        self.assertEqual(sorted(product['name'] for product in data['products']), ['Мляко', 'Сапун'])
        self.assertEqual(self.basket_names(self.alice), ['Кошница на Алис'])

    def test_prices_tab_lists_only_own_household_baskets(self):
        home_basket = HouseholdInflationBasket.objects.create(household=self.household, name='Домашна кошница')
        HouseholdInflationBasketItem.objects.create(
            basket=home_basket, product=self.household_inventory(self.household, self.milk))
        erin = make_user('erin@example.com', 'Erin')
        erin_home = make_household(erin, 'erin_home')
        foreign = HouseholdInflationBasket.objects.create(household=erin_home, name='Чужда домашна кошница')
        HouseholdInflationBasketItem.objects.create(
            basket=foreign, product=self.household_inventory(erin_home, self.milk))
        self.assertEqual(self.basket_names(self.carol), ['Домашна кошница'])
        self.assertEqual(self.basket_names(self.dave), ['Домашна кошница'])

    def test_price_history_and_changes(self):
        from datetime import timedelta
        make_purchase(self.alice, self.milk, price=12, on_date=self.day - timedelta(days=40))
        make_purchase(self.bob, self.milk, price=999, on_date=self.day - timedelta(days=20))
        data = self.data(self.alice, 'reports_prices', {'product': self.milk.pk})
        self.assertEqual([point['price'] for point in data['history']['points']], [12.0, 10.0])
        change = data['changes_table'].rows[0]
        self.assertEqual((change['product'], change['first'], change['last'], change['pct']), ('Мляко', 12.0, 10.0, -16.7))
        self.assertEqual([row['product'] for row in data['decreases']], ['Мляко'])
        foreign = Product.objects.create(name='Чужд продукт')
        make_purchase(self.bob, foreign, price=1, on_date=self.day)
        self.assertIsNone(self.data(self.alice, 'reports_prices', {'product': foreign.pk})['history'])

    # -- budget ------------------------------------------------------------------------------------
    def test_budget_tab_compares_the_periods_share_of_the_plan(self):
        import calendar
        from budget.models import Budget, BudgetIncomeItem, BudgetItem
        from income.models import IncomeType
        today = date.today()
        year_days = 366 if calendar.isleap(today.year) else 365
        budget = Budget.objects.create(name='Годишен', creator=self.alice, currency='EUR', submitted=True,
                                       date_from=date(today.year, 1, 1), date_to=date(today.year, 12, 31))
        BudgetItem.objects.create(budget=budget, category=self.main_food, planned_amount=year_days)       # 1 a day
        BudgetIncomeItem.objects.create(budget=budget, income_type=IncomeType.objects.get(name='Заплата'),
                                        planned_amount=year_days * 2)
        foreign = Budget.objects.create(name='На Боб', creator=self.bob, currency='EUR', submitted=True,
                                        date_from=date(today.year, 1, 1), date_to=date(today.year, 12, 31))
        BudgetItem.objects.create(budget=foreign, category=self.main_food, planned_amount=999999)

        result = self.data(self.alice, 'reports_budget', {'period': 'this_month'})['result']
        days = today.day
        self.assertEqual(result['budget'], budget)
        rows = {row['category']: row for row in result['rows']}
        self.assertEqual((rows['Храна']['planned'], rows['Храна']['actual'], rows['Храна']['over']),
                         (float(days), 10.0, 10.0 > days))
        self.assertEqual((rows['Дом']['planned'], rows['Дом']['actual'], rows['Дом']['over']), (0.0, 5.0, True))
        self.assertEqual((result['planned_income'], result['actual_income']), (float(days * 2), 111.0))
        self.assertIsNone(self.data(self.dave, 'reports_budget')['result'])

    # -- export ------------------------------------------------------------------------------------
    def test_export_csv_and_xlsx_contain_only_own_rows(self):
        import io

        from openpyxl import load_workbook
        self.client.force_login(self.alice)
        url = reverse('reports_categories')
        csv_response = self.client.get(url, {'export': 'products', 'format': 'csv'})
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn('text/csv', csv_response['Content-Type'])
        self.assertIn('products.csv', csv_response['Content-Disposition'])
        lines = csv_response.content.decode('utf-8-sig').strip().splitlines()
        self.assertEqual(len(lines), 3)                                  # header + milk + soap
        self.assertIn('Мляко;Млечни;1.0;1;10.0;10.0', lines)

        xlsx_response = self.client.get(url, {'export': 'year_over_year', 'format': 'xlsx'})
        self.assertIn('spreadsheetml', xlsx_response['Content-Type'])
        sheet = load_workbook(io.BytesIO(xlsx_response.content)).active
        rows = list(sheet.iter_rows(values_only=True))
        self.assertEqual(rows[1][:2], ('Храна', 10))
        self.assertEqual(rows[-1][:2], ('Общо', 15))

        self.assertEqual(self.client.get(url, {'export': 'nope'}).status_code, 404)
        for name, table in [('reports_home', 'income_and_spending_by_month'), ('reports_shops', 'shops'),
                            ('reports_prices', 'price_changes'), ('reports_cash_flow', 'cash_flow'),
                            ('reports_budget', 'budget_vs_actual')]:
            with self.subTest(table=table):
                self.assertEqual(self.client.get(reverse(name), {'export': table}).status_code, 200)

    # -- currency warnings -------------------------------------------------------------------------
    def test_missing_rate_shows_a_warning_banner_on_every_tab(self):
        make_purchase(self.alice, self.milk, price=7, currency='USD', on_date=self.day)
        for name in HUB_TABS:
            with self.subTest(view=name):
                self.assertContains(self.get_as(self.alice, name), 'USD → EUR')
        # the USD purchase is left out, never added 1:1
        self.assertEqual(self.data(self.alice, 'reports_home')['kpi']['spent'], 15.0)
        self.assertNotContains(self.get_as(self.bob, 'reports_home'), 'alert-warning')

    def test_amounts_follow_the_selected_currency(self):
        data = self.data(self.alice, 'reports_home', {'currency': 'BGN'})
        self.assertEqual(data['kpi']['spent'], 29.34)                    # 15 EUR at the fixed peg

    # -- page -------------------------------------------------------------------------------------
    def test_hub_page_has_tabs_filters_and_one_pinned_chart_library(self):
        response = self.get_as(self.alice, 'reports_home', {'period': '6m', 'scope': 'mine'})
        for text in ['Обзор', 'Категории', 'Магазини', 'Цени и инфлация', 'Паричен поток', 'Бюджет',
                     'name="scope"', 'name="currency"', 'period=12m', 'highcharts@11.4.8/', 'js/hrp-charts.js',
                     'export=largest_purchases']:
            with self.subTest(text=text):
                self.assertContains(response, text)
        # links to the other tabs keep the chosen filters
        self.assertContains(response, reverse('reports_shops') + '?period=6m&amp;scope=mine')
        self.assertNotContains(response, 'chart.js')

    # -- inflation baskets -------------------------------------------------------------------------
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
        self.assertContains(response, 'checked')

    def test_save_and_edit_basket(self):
        mine = self.user_inventory(self.alice, self.milk)
        other = self.user_inventory(self.alice, self.soap)
        self.client.force_login(self.alice)
        response = self.client.post(reverse('save_inflation_basket'), {'name': 'Моята', 'product_id[]': [mine.pk]})
        self.assertRedirects(response, reverse('reports_prices'), fetch_redirect_response=False)
        basket = UserInflationBasket.objects.get(user=self.alice, name='Моята')
        self.assertEqual([item.product_id for item in basket.user_basket_items.all()], [mine.pk])
        self.client.post(reverse('edit_inflation_basket', kwargs={'basket_id': basket.pk}),
                         {'name': 'Нова', 'product_id[]': [other.pk]})
        basket.refresh_from_db()
        self.assertEqual((basket.name, [item.product_id for item in basket.user_basket_items.all()]),
                         ('Нова', [other.pk]))
        # a second basket with the same name is refused with a message instead of a server error
        response = self.client.post(reverse('save_inflation_basket'), {'name': 'Нова'})
        self.assertRedirects(response, reverse('create_inflation_basket'), fetch_redirect_response=False)
        self.assertEqual(UserInflationBasket.objects.filter(user=self.alice).count(), 1)

    def test_save_basket_rejects_foreign_inventory_products(self):
        foreign = self.user_inventory(self.bob, self.soap)
        self.client.force_login(self.alice)
        self.client.post(reverse('save_inflation_basket'), {'name': 'Чужда', 'product_id[]': [foreign.pk]})
        self.assertFalse(UserInflationBasketItem.objects.filter(product=foreign).exists())

    def test_foreign_basket_cannot_be_opened_or_changed(self):
        basket = self.make_user_basket(self.bob, 'Кошница на Боб', self.milk)
        self.client.force_login(self.alice)
        url = reverse('edit_inflation_basket', kwargs={'basket_id': basket.pk})
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {'name': 'Хак'}).status_code, 404)
        basket.refresh_from_db()
        self.assertEqual(basket.name, 'Кошница на Боб')
        self.assertEqual(basket.user_basket_items.count(), 1)

    def test_two_users_can_use_the_same_basket_name(self):
        UserInflationBasket.objects.create(user=self.alice, name='Храна')
        with transaction.atomic():
            UserInflationBasket.objects.create(user=self.bob, name='Храна')
        self.assertEqual(UserInflationBasket.objects.filter(name='Храна').count(), 2)
