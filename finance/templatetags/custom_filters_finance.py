from django import template

register = template.Library()

@register.filter
def billions(value):
    try:
        return round(float(value) / 1_000_000_000, 2)
    except (ValueError, TypeError):
        return value