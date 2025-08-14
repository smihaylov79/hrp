from django import template
from finance.models import Market, MarginGroups

register = template.Library()

@register.filter
def billions(value):
    try:
        return round(float(value) / 1_000_000_000, 2)
    except (ValueError, TypeError):
        return value


@register.filter
def convert_percentage(value):
    try:
        return round(float(value) * 100, 2)
    except (ValueError, TypeError):
        return value


@register.filter
def get_exchange(value):
    market = Market.objects.filter(long_name=value).first()

    if market:
        return {
            'name': market.name,
            'status': 'open' if market.is_open_now() else 'closed'
        }
    return {'name': '-', 'status': 'unknown'}


@register.filter
def get_margin(value):
    group = MarginGroups.objects.filter(name=value).first()
    if group:
        return group.ratio
    return '-'

