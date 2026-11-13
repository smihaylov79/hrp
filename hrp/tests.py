from unittest import mock

from django.test import SimpleTestCase

from hrp.settings import env_bool
from django.urls import reverse

from hrp.testing import HrpTestCase, make_purchase


class FinanceUnpluggedTests(HrpTestCase):
    """The finance app is unplugged: no URL, no nav item, no home card, no HTTP ping on every page."""

    def test_finance_is_not_installed_or_routed(self):
        from django.apps import apps
        self.assertFalse(apps.is_installed('finance'))
        self.assertEqual(self.client.get('/finance/').status_code, 404)

    def test_home_and_navbar_have_no_finance_links(self):
        for user in (None, self.alice):
            with self.subTest(user=user):
                if user:
                    self.client.force_login(user)
                response = self.client.get('/')
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, '/finance/')
                self.assertNotIn('server_status', response.context)

    def test_pages_render_without_any_outbound_request_from_context_processors(self):
        self.client.force_login(self.alice)
        with mock.patch('requests.sessions.Session.request') as request:
            self.assertEqual(self.client.get('/reports/').status_code, 200)
        request.assert_not_called()


class ShellAndDashboardTests(HrpTestCase):
    """New base layout (sidebar, top bar, toasts) and the home page as a dashboard."""

    def test_shell_has_grouped_navigation_theme_and_pinned_assets(self):
        self.client.force_login(self.alice)
        response = self.client.get('/reports/')
        for text in ['hrp-sidebar', 'navOffcanvas', 'themeToggle', 'css/theme.css', 'bootstrap@5.3.3', 'integrity="sha384-',
                     'Пари', 'Дом', 'Свободно време', 'Калкулатор за ресто', 'name="language"']:
            with self.subTest(text=text):
                self.assertContains(response, text)
        self.assertContains(response, 'class="active"><i class="bi bi-bar-chart-line">')   # current section is marked
        self.assertNotContains(response, 'navbar-dark')

    def test_anonymous_visitor_sees_landing_page_with_login_links(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('login'))
        self.assertContains(response, reverse('register'))
        self.assertNotContains(response, 'Похарчено този месец')
        self.assertNotContains(response, 'hrp-search')

    def test_dashboard_shows_only_own_month_spending_tasks_and_stock(self):
        from datetime import date, timedelta
        from decimal import Decimal
        from taskmanager.models import Task
        today = date.today()
        make_purchase(self.alice, self.milk, price=40, on_date=today)
        make_purchase(self.alice, self.soap, price=999, on_date=today.replace(day=1) - timedelta(days=1))   # last month
        make_purchase(self.bob, self.milk, price=5000, on_date=today)
        Task.objects.create(user=self.alice, title='Моя задача', due_date=today)
        Task.objects.create(user=self.alice, title='Стара задача', due_date=today - timedelta(days=3))
        Task.objects.create(user=self.alice, title='Готова', due_date=today, completed=True)
        Task.objects.create(user=self.bob, title='Чужда задача', due_date=today)
        low = self.user_inventory(self.alice, self.milk, quantity=1)
        type(low).objects.filter(pk=low.pk).update(minimum_quantity=Decimal('3'))
        foreign = self.user_inventory(self.bob, self.soap, quantity=0)
        type(foreign).objects.filter(pk=foreign.pk).update(minimum_quantity=Decimal('3'))

        self.client.force_login(self.alice)
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['month_total'], 40.0)
        self.assertEqual((response.context['tasks_today'], response.context['tasks_overdue']), (1, 1))
        self.assertEqual([row['task'].title for row in response.context['task_rows']], ['Стара задача', 'Моя задача'])
        self.assertEqual([item.product.name for item in response.context['low_stock']], ['Мляко'])
        self.assertNotContains(response, 'Чужда задача')
        self.assertContains(response, 'няма активен бюджет')

    def test_dashboard_budget_progress_uses_the_monthly_share_of_the_budget(self):
        import calendar
        from datetime import date
        from budget.models import Budget, BudgetItem
        today = date.today()
        year_days = 366 if calendar.isleap(today.year) else 365
        budget = Budget.objects.create(name='Годишен', creator=self.alice, currency='EUR', submitted=True,
                                       date_from=date(today.year, 1, 1), date_to=date(today.year, 12, 31))
        BudgetItem.objects.create(budget=budget, category=self.main_food, planned_amount=year_days * 10)
        make_purchase(self.alice, self.milk, price=31, on_date=today)        # category "Храна"
        self.client.force_login(self.alice)
        progress = self.client.get('/').context['budget_progress']
        days = calendar.monthrange(today.year, today.month)[1]
        self.assertEqual(progress['rows'][0]['name'], 'Храна')
        self.assertEqual(progress['rows'][0]['planned'], days * 10)          # 10 per day
        self.assertEqual(progress['rows'][0]['spent'], 31)
        self.assertEqual(progress['budget'], budget)

    def test_dashboard_for_a_new_user_and_query_budget(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        self.client.force_login(self.bob)
        self.client.get('/')
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(ctx), 20, f'home ran {len(ctx)} queries')
        self.assertContains(response, 'Всичко е налично.')

    def test_messages_are_shown_as_toasts(self):
        from django.contrib import messages
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.template.loader import render_to_string
        from django.test import RequestFactory
        request = RequestFactory().get('/')
        request.session = self.client.session
        request.user = self.alice
        request._messages = FallbackStorage(request)
        messages.success(request, 'Списъкът е генериран')
        html = render_to_string('includes/messages.html', request=request)
        self.assertIn('Списъкът е генериран', html)
        self.assertIn('toast', html)

    def test_search_finds_only_own_products_tasks_and_all_recipes(self):
        from cooking.models import Recipe, RecipeCategory
        from shopping.models import Product
        from taskmanager.models import Task
        make_purchase(self.alice, self.milk, price=1)
        only_bob = Product.objects.create(name='Млечен шоколад', category=self.cat_dairy)
        make_purchase(self.bob, only_bob, price=1)
        Recipe.objects.create(name='Млечна баница', category=RecipeCategory.objects.create(name='Тестени'))
        Task.objects.create(user=self.alice, title='Купи мляко')
        Task.objects.create(user=self.bob, title='Мляко за Боб')
        self.assertLoginRequired(reverse('search') + '?q=мл')
        self.client.force_login(self.alice)
        response = self.client.get(reverse('search'), {'q': 'мл'})
        self.assertEqual([p.name for p in response.context['products']], ['Мляко'])
        self.assertEqual([r.name for r in response.context['recipes']], ['Млечна баница'])
        self.assertEqual([t.title for t in response.context['tasks']], ['Купи мляко'])
        self.assertEqual(self.client.get(reverse('search'), {'q': 'м'}).context['result_count'], 0)


class SettingsTests(SimpleTestCase):
    def test_locale_middleware_is_between_session_and_common(self):
        from django.conf import settings
        order = settings.MIDDLEWARE.index
        self.assertLess(order('django.contrib.sessions.middleware.SessionMiddleware'),
                        order('django.middleware.locale.LocaleMiddleware'))
        self.assertLess(order('django.middleware.locale.LocaleMiddleware'),
                        order('django.middleware.common.CommonMiddleware'))

    def test_cache_is_shared_between_workers(self):
        from django.conf import settings
        self.assertIn('DatabaseCache', settings.CACHES['default']['BACKEND'])


class EnvBoolTests(SimpleTestCase):
    """DEBUG=False in .env must really switch DEBUG off (any non-empty string used to be truthy)."""

    def parse(self, value):
        env = {} if value is None else {'X': value}
        with mock.patch.dict('os.environ', env, clear=True):
            return env_bool('X')

    def test_false_like_values(self):
        for value in [None, '', 'False', 'false', '0', 'no', 'off', 'anything']:
            with self.subTest(value=value):
                self.assertIs(self.parse(value), False)

    def test_true_like_values(self):
        for value in ['True', 'true', 'TRUE', '1', 'yes', ' true ']:
            with self.subTest(value=value):
                self.assertIs(self.parse(value), True)
