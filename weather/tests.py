from unittest import mock

import requests
from django.core.cache import cache
from django.test import RequestFactory, TestCase

from .views import get_weather_data


class WeatherRequestTests(TestCase):
    def request(self, city=None):
        request = RequestFactory().get('/')
        request.session = {'geo_location': city} if city else {}
        return request

    def ok_response(self, get):
        get.return_value.status_code = 200
        get.return_value.json.return_value = {'forecast': {'forecastday': []}}

    def test_api_is_called_over_https_with_a_timeout(self):
        with mock.patch('weather.views.requests.get') as get:
            self.ok_response(get)
            get_weather_data(self.request())
        args, kwargs = get.call_args
        self.assertTrue(args[0].startswith('https://'))
        self.assertTrue(kwargs.get('timeout'))

    def test_network_failure_gives_an_error_message_not_a_crash(self):
        with mock.patch('weather.views.requests.get', side_effect=requests.exceptions.Timeout):
            data = get_weather_data(self.request())
        self.assertIn('error', data)

    def test_forecast_is_cached_per_city(self):
        with mock.patch('weather.views.requests.get') as get:
            self.ok_response(get)
            get_weather_data(self.request('Sofia'))
            get_weather_data(self.request('sofia '))      # same city, different spelling of the key
            self.assertEqual(get.call_count, 1)
            get_weather_data(self.request('Varna'))
            self.assertEqual(get.call_count, 2)

    def test_failures_are_not_cached(self):
        with mock.patch('weather.views.requests.get', side_effect=requests.exceptions.Timeout) as get:
            get_weather_data(self.request('Plovdiv'))
            get_weather_data(self.request('Plovdiv'))
            self.assertEqual(get.call_count, 2)
