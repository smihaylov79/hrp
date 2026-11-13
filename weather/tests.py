from unittest import mock

import requests
from django.test import RequestFactory, SimpleTestCase

from .views import get_weather_data


class WeatherRequestTests(SimpleTestCase):
    def request(self):
        request = RequestFactory().get('/')
        request.session = {}
        return request

    def test_api_is_called_over_https_with_a_timeout(self):
        with mock.patch('weather.views.requests.get') as get:
            get.return_value.status_code = 200
            get.return_value.json.return_value = {'forecast': {'forecastday': []}}
            get_weather_data(self.request())
        args, kwargs = get.call_args
        self.assertTrue(args[0].startswith('https://'))
        self.assertTrue(kwargs.get('timeout'))

    def test_network_failure_gives_an_error_message_not_a_crash(self):
        with mock.patch('weather.views.requests.get', side_effect=requests.exceptions.Timeout):
            data = get_weather_data(self.request())
        self.assertIn('error', data)
