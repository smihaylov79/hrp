from decimal import Decimal
import os

import requests
from bs4 import BeautifulSoup
import re
from django.db.models import TextChoices

from inventory.models import HouseholdInventoryProduct, HouseholdProductCategory, InventoryProduct, UserProductCategory
from reports.models import ExchangeRate
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


def fetch_rate_from_api(base_currency, target_currency, date):
    API_EXCHANGE_RATES = os.environ.get('API_EXCHANGE_RATES')
    url = (f"https://api.exchangerate.host/convert"
        f"?from={base_currency}&to={target_currency}&date={date}&amount=1"
        f"&access_key={API_EXCHANGE_RATES}")
    response = requests.get(url)
    data = response.json()

    rate = data.get('info', {}).get('quote')

    if data.get("success") and rate:
        return rate
    raise ValueError("Failed to extract data")


def get_exchange_rate(base_currency, target_currency, date):
    rate = ExchangeRate.objects.filter(base_currency=base_currency, target_currency=target_currency, date_extracted=date).first()
    if rate:

        return rate.rate

    rate = fetch_rate_from_api(base_currency, target_currency, date)
    ExchangeRate.objects.create(base_currency=base_currency, target_currency=target_currency, rate=rate, date_extracted=date)

    return rate


def fetch_electricity_price():
    url = "https://euenergy.live/electricity-prices/bulgaria/sofia"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    subline_paragraphs = soup.find_all('p', class_='subline')

    if subline_paragraphs:
        spans = subline_paragraphs[0].find_all('span')
        if len(spans) >= 2:
            price_kwh = spans[1].text.strip()
            price_kwh = price_kwh.replace('€ ', '')
            return round(float(price_kwh) * 1.95583, 2)



def fetch_cold_water():
    url = "https://www.sofiyskavoda.bg/en/water-tariff"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    td_blocks = soup.find_all('td', class_='table-header-block')
    for td in td_blocks:
        if "Total (supply, sewerage, treatment)" in td.text:

            td_with_price = td.find_next_sibling('td').find_next_sibling('td')
            if td_with_price:
                divs = td_with_price.find_all('div')
                for div in divs:
                    try:
                        price = round(float(div.text.strip())/1.95583, 2)
                        return price
                    except ValueError:
                        continue
    return None


def get_heating_price():
    url = "https://toplo.bg/prices"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    price_tags = soup.find_all('p', class_='red-text red-text-price')

    for tag in price_tags:
        match = re.search(r'(\d{2,3}[.,]\d{2})\s*лева', tag.text)
        if match:
            return float(match.group(1).replace(',', '.'))

    return None

