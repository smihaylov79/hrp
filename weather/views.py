from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils.timezone import now
import requests
from django.utils.timezone import now
from datetime import datetime
import os

# Create your views here.


def get_weather_data(request):
    api_key = os.environ.get('API_KEY_WEATHER')
    location = request.session.get("geo_location", "Sofia")
    if not location:
        location = "Sofia"
    url = f"http://api.weatherapi.com/v1/forecast.json?key={api_key}&q={location}&days=4"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        request.session["geo_location"] = "Sofia"  # Fallback silently
        return {"error": "Градът не беше намерен. Показвам прогнозата за София."}


def weather_data_context_processor(request):
    weather_data = get_weather_data(request)
    error_message = None

    if weather_data and 'forecast' in weather_data:

        forecast = weather_data.get('forecast', {})
        for day in forecast.get('forecastday', []):
            date_str = day.get('date')
            if date_str:
                day['parsed_date'] = datetime.strptime(date_str, "%Y-%m-%d")

    elif weather_data and 'error' in weather_data:
        error_message = weather_data['error']
        weather_data = None

    return {
        'weather_data': weather_data,
        'weather_error': error_message,
        'now': now(),
    }


def set_location(request):
    city = request.GET.get("location", "Sofia")
    request.session["geo_location"] = city
    return redirect(request.META.get('HTTP_REFERER', '/'))


def detailed_forecast(request, date):
    weather_data = get_weather_data(request)
    forecast_day = None
    formated_day = None

    if weather_data:
        for day in weather_data['forecast']['forecastday']:
            if day['date'] == date:
                formated_day = datetime.strptime(day['date'], "%Y-%m-%d")
                forecast_day = day
                break
    context = {'formated_day':formated_day, 'forecast_day': forecast_day,
        'location': weather_data.get('location') if weather_data else None}

    return render(request, 'weather/detailed_forecast.html', context)
