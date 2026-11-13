from datetime import datetime
from decimal import Decimal
import os
import requests
from django.core.cache import cache
from bs4 import BeautifulSoup
import re
from inventory.models import HouseholdInventoryProduct, HouseholdProductCategory, InventoryProduct, UserProductCategory
from shopping.models import HouseholdShoppingList, ShoppingList, Product, ShoppingProduct, Shopping


def load_prefill_data(request, user, household):
    selected_list_id = request.GET.get("list")
    prefill_data = []

    if not selected_list_id:
        return prefill_data

    else:
        try:
            if household:
                shopping_list = HouseholdShoppingList.objects.get(id=selected_list_id, household=household)
            else:
                shopping_list = ShoppingList.objects.get(id=selected_list_id, user=user)
            for item_name in shopping_list.items:
                item_name = item_name.split('(')[0].strip()
                product = Product.objects.filter(name=item_name).first()
                if product:
                    last_price = 0.00
                    shoppings = Shopping.objects.filter(user=user)
                    shoppings_ids = [sh.id for sh in shoppings]
                    shopping_product = ShoppingProduct.objects.filter(product=product.id,
                                                                      shopping__in=shoppings_ids).order_by('id').last()
                    if shopping_product:
                        last_price = shopping_product.price
                    prefill_data.append({
                        "product_id": product.id,
                        "name": product.name,
                        "quantity": 1,
                        "price": last_price,
                        "discount": 0,
                        "not_for_household": False,
                    })
        except ShoppingList.DoesNotExist:
            pass
        return prefill_data


def save_shopping_products(selected_products, shopping, user, household):
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
        if household:
            inventory_product, created = HouseholdInventoryProduct.objects.get_or_create(
                household=household, product=product, category=product.category,
                defaults={"quantity": 0, "amount": 0, "inventory_related": True}
            )
            if inventory_product.inventory_related and not not_for_household:
                inventory_product.quantity += quantity
                inventory_product.amount += amount
                inventory_product.calculate_average_price()
                inventory_product.save()

            household_product_category, created = HouseholdProductCategory.objects.get_or_create(household=household,
                                                                                                 product_category=product.category)
            household_product_category.save()

        else:
            inventory_product, created = InventoryProduct.objects.get_or_create(
                user=user, product=product, category=product.category,
                defaults={"quantity": 0, "amount": 0, "inventory_related": True}
            )
            if inventory_product.inventory_related and not not_for_household:
                inventory_product.quantity += quantity
                inventory_product.amount += amount
                inventory_product.calculate_average_price()
                inventory_product.save()

            user_product_category, created = UserProductCategory.objects.get_or_create(user=user,
                                                                                       product_category=product.category)
            user_product_category.save()


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

