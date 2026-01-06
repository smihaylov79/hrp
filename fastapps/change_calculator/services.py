from decimal import Decimal

import requests

from reports.models import ExchangeRate

# ECB_URL = "https://api.exchangerate.host/latest"
#
#
# def convert(amount, from_currency, to_currency):
#     rate = ExchangeRate.objects.filter(base_currency=from_currency, target_currency=to_currency).order_by('-date_extracted').first()
#     rates = Decimal(1.95583)
#     in_target_currency = amount * rate
#
#     return in_target_currency


def convert(amount, from_currency, to_currency):
    amount = Decimal(amount)

    # Same currency → no conversion
    if from_currency == to_currency:
        return amount

    # Try direct rate: from → to
    direct = ExchangeRate.objects.filter(
        base_currency=from_currency,
        target_currency=to_currency
    ).order_by('-date_extracted').first()

    if direct:
        return amount * direct.rate

    # Try reverse rate: to → from
    reverse = ExchangeRate.objects.filter(
        base_currency=to_currency,
        target_currency=from_currency
    ).order_by('-date_extracted').first()

    if reverse:
        return amount / reverse.rate

    # Try indirect conversion via EUR (or any base you use)
    # Example: USD → EUR → BGN
    eur_from = ExchangeRate.objects.filter(
        base_currency=from_currency,
        target_currency="EUR"
    ).order_by('-date_extracted').first()

    eur_to = ExchangeRate.objects.filter(
        base_currency="EUR",
        target_currency=to_currency
    ).order_by('-date_extracted').first()

    if eur_from and eur_to:
        amount_in_eur = amount * eur_from.rate
        return amount_in_eur * eur_to.rate

    raise ValueError(f"No exchange rate available for {from_currency} → {to_currency}")



