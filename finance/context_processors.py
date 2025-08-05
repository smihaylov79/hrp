import requests
from django.conf import settings


def fastapi_url(request):
    try:
        response = requests.get(f"{settings.FAST_API_URL.rstrip('/')}/ping")
        data = response.text.strip().lower().replace('"', '')
        if data in ['invest', 'trade']:
            status = data
        else:
            status = 'offline'
    except Exception as e:
        status = 'offline'
    return {'server_status': status}
