from django.conf import settings


def fastapi_url(request):
    return {
        'fastapi_url': f"{settings.FAST_API_URL.rstrip('/')}/ping"
    }