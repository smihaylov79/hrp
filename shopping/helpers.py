from datetime import datetime
from decimal import Decimal
import os
import requests
from django.core.cache import cache
from bs4 import BeautifulSoup
import re
from inventory.models import HouseholdInventoryProduct, HouseholdProductCategory, InventoryProduct, UserProductCategory
from shopping.models import HouseholdShoppingList, ShoppingList, Product, ShoppingProduct


def load_prefill_data(request, user, household):
    """Rows for the "new purchase" form from a generated shopping list, with the last price paid.

    The last price is the household's (or the user's) most recent purchase of the product. Three queries in
    total, however long the list is.
    """
    selected_list_id = request.GET.get("list")
    if not selected_list_id or not str(selected_list_id).isdigit():
        return []

    if household:
        shopping_list = HouseholdShoppingList.objects.filter(id=selected_list_id, household=household).first()
        purchases = ShoppingProduct.objects.filter(shopping__user__household=household)
    else:
        shopping_list = ShoppingList.objects.filter(id=selected_list_id, user=user).first()
        purchases = ShoppingProduct.objects.filter(shopping__user=user)
    if shopping_list is None:
        return []

    # list items look like "Мляко (1.25 €)": the product name is the part before the bracket
    names = [item_name.split('(')[0].strip() for item_name in shopping_list.items]
    products = {product.name: product for product in Product.objects.filter(name__in=names).only("id", "name")}

    last_price = {}
    for product_id, price in (purchases.filter(product__in=[product.id for product in products.values()])
                              .order_by('product_id', '-shopping__date', '-id').values_list('product_id', 'price')):
        last_price.setdefault(product_id, price)       # first row per product = the newest purchase

    prefill_data = []
    for name in names:
        product = products.get(name)
        if product:
            prefill_data.append({
                "product_id": product.id,
                "name": product.name,
                "quantity": 1,
                "price": last_price.get(product.id, 0.00),
                "discount": 0,
                "not_for_household": False,
            })
    return prefill_data


def inventory_row(model, owner, product):
    """The inventory row of ``product`` for one owner ({'user': ...} or {'household': ...}).

    There must be one row per owner and product. The row is looked up by owner + product only - not by
    category - so that moving a product to another category does not create a second row; the row's
    category then follows the product. If older duplicates exist, the oldest row is used.
    """
    row = model.objects.filter(product=product, **owner).order_by('id').first()
    if row is None:
        return model.objects.create(product=product, category=product.category, quantity=0, amount=0,
                                    inventory_related=True, **owner)
    if row.category_id != product.category_id:
        row.category = product.category
        row.save(update_fields=['category'])
    return row


def save_shopping_products(selected_products, shopping, user, household):
    if household:
        inventory_model, category_model, owner = HouseholdInventoryProduct, HouseholdProductCategory, {'household': household}
    else:
        inventory_model, category_model, owner = InventoryProduct, UserProductCategory, {'user': user}

    for product_data in selected_products:
        product = Product.objects.get(id=product_data["product_id"])
        quantity = Decimal(product_data["quantity"])
        price = Decimal(product_data["price"])
        discount = Decimal(product_data["discount"] if product_data["discount"] else 0)
        amount = quantity * price - discount

        not_for_household = product_data['not_for_household']

        ShoppingProduct.objects.create(
            shopping=shopping, product=product, quantity=quantity, price=price,
            discount=discount, amount=amount, not_for_household=not_for_household
        )
        inventory_product = inventory_row(inventory_model, owner, product)
        if inventory_product.inventory_related and not not_for_household:
            inventory_product.quantity += quantity
            inventory_product.amount += amount
            inventory_product.calculate_average_price()      # also saves the row

        category_model.objects.get_or_create(product_category=product.category, **owner)


PRICE_CACHE_SECONDS = 24 * 60 * 60
PRICE_FAILURE_SECONDS = 15 * 60


def cached_price(name, fetch):
    """Result of ``fetch()`` cached for a day; a failure ("no data"/None/exception) is remembered for 15 minutes
    so that a slow or dead external site does not delay every page load."""
    key = f"utility_price:{name}"
    cached = cache.get(key)
    if cached is not None:
        return None if cached == "__failed__" else cached
    try:
        value = fetch()
    except Exception:
        value = None
    if value in (None, "no data"):
        cache.set(key, "__failed__", PRICE_FAILURE_SECONDS)
        return None
    cache.set(key, value, PRICE_CACHE_SECONDS)
    return value


def fetch_electricity_price():
    url = f"https://api.energy-charts.info/price?country=bg&year={datetime.now().year}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # catches 4xx/5xx errors
        data = response.json()

        if data and "price" in data and data["price"]:
            price = data["price"][-1] / 1000
            return round(price, 2)

        return "no data"

    except (requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
            ValueError, KeyError):
        return "no data"




def fetch_cold_water():
    # url = "https://www.sofiyskavoda.bg/en/water-tariff"
    # # response = requests.get(url)
    # try:
    #     response = requests.get(url, timeout=10)
    #     response.raise_for_status()
    # except Exception:
    #     return "no data"
    # soup = BeautifulSoup(response.text, 'html.parser')
    #
    # td_blocks = soup.find_all('td', class_='table-header-block')
    # for td in td_blocks:
    #     if "Total (supply, sewerage, treatment)" in td.text:
    #
    #         td_with_price = td.find_next_sibling('td').find_next_sibling('td')
    #         if td_with_price:
    #             text = td_with_price.get_text(" ", strip=True)
    #             match = re.search(r"(\d+\.\d+)\s*€", text)
    #             if match:
    #                 return float(match.group(1))
    return 2.111


def get_heating_price():
    url = "https://toplo.bg/prices"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')

    price_tags = soup.find_all('p', class_='red-text red-text-price')

    for tag in price_tags:
        match = re.search(r'(\d{2,3}[.,]\d{2})\s*€', tag.text)
        if match:
            return float(match.group(1).replace(',', '.'))

    return None

