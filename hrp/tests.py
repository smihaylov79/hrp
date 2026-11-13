from unittest import mock

from django.test import SimpleTestCase

from hrp.settings import env_bool


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
