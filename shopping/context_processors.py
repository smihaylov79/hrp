from django.utils.timezone import now


def current_datetime(request):
    return {'now': now()}
