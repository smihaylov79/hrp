from django.utils.timezone import now

from shopping.models import BasketItem

def basket_item_count(request):
    if request.user.is_authenticated:
        return {"basket_item_count": BasketItem.objects.filter(basket__user=request.user).count()}
    return {"basket_item_count": 0}


def current_datetime(request):
    return {'now': now()}
