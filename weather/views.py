from django.http import JsonResponse
from django.shortcuts import render
from django.utils.timezone import now
import requests
from django.utils.timezone import now
from datetime import datetime
import os

# Create your views here.


def get_weather_data(request):
    api_key = os.environ.get('API_KEY_WEATHER')
    location = request.session.get("geo_location", "Sofia")
    url = f"http://api.weatherapi.com/v1/forecast.json?key={api_key}&q={location}&days=4"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return None


def weather_data_context_processor(request):
    weather_data = get_weather_data(request)

    if weather_data:
        for forecast_day in weather_data['forecast']['forecastday']:
            forecast_day['parsed_date'] = datetime.strptime(forecast_day['date'], "%Y-%m-%d")

    return {
        'weather_data': weather_data,
        'now': now()
    }


def set_location(request):
    lat = request.GET.get("lat")
    lon = request.GET.get("lon")
    request.session["geo_location"] = f"{lat},{lon}"
    return JsonResponse({"status": "ok"})


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
