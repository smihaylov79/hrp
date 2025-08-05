from reports.models import ExchangeRate
from weather.views import get_weather_data
from datetime import datetime
from django.utils.timezone import now


def collect_weather_data(request):
    weather_data = get_weather_data(request)
    error_message = None
    rate = ExchangeRate.objects.filter(target_currency='USD').order_by('-date_extracted').first()

    if weather_data and 'forecast' in weather_data:

        forecast = weather_data.get('forecast', {})
        for day in forecast.get('forecastday', []):
            date_str = day.get('date')
            if date_str:
                day['parsed_date'] = datetime.strptime(date_str, "%Y-%m-%d")

    elif weather_data and 'error' in weather_data:
        error_message = weather_data['error']
        weather_data = None

    current_time = now()

    return weather_data, error_message, current_time, rate
