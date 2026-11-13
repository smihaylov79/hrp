"""Downloading and storing exchange rates (used by the fetch_rates command, never during a page request).

Only EUR -> X is stored for every currency X that is not pegged to the euro; reports/currency.py derives all
other pairs (inverse, BGN through the peg) from it.
"""
import os
from datetime import date
from decimal import Decimal

import requests

from shopping.models import CurrencyChoice

from .currency import PEGGED, PIVOT
from .models import ExchangeRate

TIMEOUT = 10


class RateFetchError(Exception):
    pass


def foreign_currencies():
    """Currencies whose rate has to be downloaded (everything except EUR and BGN)."""
    return [code for code in CurrencyChoice.values if code not in PEGGED]


def _from_frankfurter(on_date, currencies):
    """European Central Bank reference rates, no API key. Weekends/holidays return the previous working day."""
    response = requests.get(f"https://api.frankfurter.dev/v1/{on_date.isoformat()}",
                            params={"base": PIVOT, "symbols": ",".join(currencies)}, timeout=TIMEOUT)
    response.raise_for_status()
    rates = response.json().get("rates") or {}
    return {code: Decimal(str(rates[code])) for code in currencies if rates.get(code)}


def _from_exchangerate_host(on_date, currencies):
    key = os.environ.get("API_EXCHANGE_RATES")
    if not key:
        return {}
    found = {}
    for code in currencies:
        response = requests.get("https://api.exchangerate.host/convert",
                                params={"from": PIVOT, "to": code, "date": on_date.isoformat(), "amount": 1,
                                        "access_key": key}, timeout=TIMEOUT)
        data = response.json()
        quote = (data.get("info") or {}).get("quote")
        if data.get("success") and quote:
            found[code] = Decimal(str(quote))
    return found


def fetch_eur_rates(on_date=None, currencies=None):
    """{currency: Decimal rate for 1 EUR} on ``on_date``. Raises RateFetchError if a currency is not available."""
    on_date = on_date or date.today()
    currencies = list(currencies or foreign_currencies())
    found, errors = {}, []
    for source in (_from_frankfurter, _from_exchangerate_host):
        missing = [code for code in currencies if code not in found]
        if not missing:
            break
        try:
            found.update(source(on_date, missing))
        except (requests.RequestException, ValueError, KeyError) as exc:
            errors.append(f"{source.__name__}: {type(exc).__name__}")
    missing = [code for code in currencies if code not in found]
    if missing:
        raise RateFetchError(f"No rate for {', '.join(missing)} on {on_date} ({'; '.join(errors) or 'not offered'})")
    return found


def store_eur_rates(on_date, rates):
    """Save {currency: rate} as EUR -> currency rows for ``on_date`` (updates the row if it already exists)."""
    stored = []
    for code, rate in rates.items():
        obj, _created = ExchangeRate.objects.update_or_create(
            base_currency=PIVOT, target_currency=code, date_extracted=on_date, defaults={"rate": rate})
        stored.append(obj)
    return stored


def fetch_and_store(on_date=None, currencies=None):
    on_date = on_date or date.today()
    return store_eur_rates(on_date, fetch_eur_rates(on_date, currencies))


def used_foreign_dates():
    """{(currency, date): number of records} for every purchase / income in a non-pegged currency."""
    from django.db.models import Count

    from income.models import Income
    from shopping.models import Shopping

    used = {}
    for row in (Shopping.objects.exclude(currency__in=PEGGED).values("currency", "date").annotate(n=Count("id"))):
        used[(row["currency"], row["date"])] = used.get((row["currency"], row["date"]), 0) + row["n"]
    for row in (Income.objects.exclude(currency__in=PEGGED).values("currency", "date_received")
                .annotate(n=Count("id"))):
        key = (row["currency"], row["date_received"])
        used[key] = used.get(key, 0) + row["n"]
    return used


def audit(max_age_days=4):
    """Check that every purchase / income in a foreign currency has a usable rate.

    Returns a list of (problem, currency, date, records, detail) where problem is
    "missing" (no rate at all), "later" (first rate is newer than the record) or "stale" (rate is older than
    ``max_age_days`` days; 4 covers a long weekend).
    """
    from .currency import RateTable

    table = RateTable.load()
    problems = []
    for (currency, day), records in sorted(used_foreign_dates().items()):
        rate_day = table.rate_day(currency, PIVOT, day)
        if rate_day is None:
            problems.append(("missing", currency, day, records, "no rate stored"))
        elif rate_day > day:
            problems.append(("later", currency, day, records, f"earliest rate is from {rate_day}"))
        elif (day - rate_day).days > max_age_days:
            problems.append(("stale", currency, day, records, f"rate from {rate_day} ({(day - rate_day).days} days older)"))
    return problems
