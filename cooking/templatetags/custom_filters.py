from django import template

register = template.Library()

@register.filter
def dict_lookup(dictionary, key):
    return dictionary.get(key, 0)  # ✅ Safely retrieves value or returns 0 if key doesn't exist
