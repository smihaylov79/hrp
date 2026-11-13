from unittest import mock

from django.test import SimpleTestCase

from hrp.settings import env_bool
from hrp.testing import HrpTestCase


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
