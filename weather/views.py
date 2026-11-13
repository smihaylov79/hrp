from django.http import JsonResponse
from django.shortcuts import render, redirect
import requests
from datetime import datetime
import hashlib
import os

from django.core.cache import cache

WEATHER_CACHE_SECONDS = 30 * 60


def get_weather_data(request):
    api_key = os.environ.get('API_KEY_WEATHER')
    location = request.session.get("geo_location", "Sofia")
    if not location:
        location = "Sofia"
    cache_key = "weather:" + hashlib.md5(location.strip().lower().encode("utf-8")).hexdigest()
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    url = "https://api.weatherapi.com/v1/forecast.json"
    try:
        response = requests.get(url, params={"key": api_key, "q": location, "days": 4}, timeout=5)
    except requests.RequestException:
        return {"error": "Прогнозата за времето не е достъпна в момента."}
    if response.status_code == 200:
        data = response.json()
        cache.set(cache_key, data, WEATHER_CACHE_SECONDS)   # the forecast is the same for everybody in a city
        return data
    else:
        request.session["geo_location"] = "Sofia"
        return {"error": "Градът не беше намерен. Показвам прогнозата за София."}


def set_location(request):
    city = request.GET.get("location", "Sofia")
    request.session["geo_location"] = city
    return redirect(request.META.get('HTTP_REFERER', '/'))


def detailed_forecast(request, date):
    weather_data = get_weather_data(request)
    forecast_day = None
    formated_day = None

    if weather_data and 'forecast' in weather_data:
        for day in weather_data['forecast']['forecastday']:
            if day['date'] == date:
                formated_day = datetime.strptime(day['date'], "%Y-%m-%d")
                forecast_day = day
                break
    context = {'formated_day':formated_day, 'forecast_day': forecast_day,
        'location': weather_data.get('location') if weather_data else None}

    return render(request, 'weather/detailed_forecast.html', context)
