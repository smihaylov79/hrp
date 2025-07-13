from django import template
from shopping.models import *

register = template.Library()

@register.filter
def dict_lookup(dictionary, key):
    return dictionary.get(key, 0)


@register.filter
def get_product_name(product_id):
    product = Product.objects.filter(id=product_id).first()
    return product.name if product else ""
