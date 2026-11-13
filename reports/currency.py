"""The single place for currency conversion.

Rules
-----
* BGN <-> EUR always uses the fixed peg (1 EUR = 1.95583 BGN). It is never read from the database.
* Every other pair comes from ``ExchangeRate``: the rate valid on the purchase date, i.e. the newest stored rate
  on or before that date (direct, or the inverse of the opposite pair, whichever is closer in time), going
  through EUR when there is no rate between the two currencies themselves.
* When the first stored rate is newer than the purchase, that earliest rate is used and the conversion is
  reported as approximate.
* A pair without any rate raises ``MissingRate``. Nothing is ever converted 1:1 silently.

All rates are loaded with ONE query, at most once per request (the table is dropped when a new request starts,
when an ``ExchangeRate`` is saved or deleted, and after ``CACHE_SECONDS`` in shells / commands). Converting a
DataFrame therefore runs no query per row.
"""
import time
from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal

from django.core.signals import request_started
from django.db.models.signals import post_delete, post_save
from django.utils.translation import gettext as _

from .models import ExchangeRate

BGN_PER_EUR = Decimal("1.95583")
PEGGED = ("BGN", "EUR")
PIVOT = "EUR"
DEFAULT_CURRENCY = "EUR"
CACHE_SECONDS = 60


class MissingRate(ValueError):
    """There is no stored exchange rate that can convert ``base`` to ``target``."""

    def __init__(self, base, target):
        self.base, self.target = base, target
        super().__init__(f"No exchange rate available for {base} → {target}")


def _as_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if hasattr(value, "date"):  # pandas Timestamp
        return value.date()
    return date.fromisoformat(str(value)[:10])


class RateTable:
    """All stored rates in memory, indexed for "rate on or before a date" lookups."""

    def __init__(self, rows):
        # {(base, target): {date: Decimal}} with every stored row and its inverse; a stored direct rate
        # wins over an inverted one for the same day.
        series = defaultdict(dict)
        inverted = defaultdict(dict)
        for base, target, rate, day in rows:
            if base == target or not rate or (base in PEGGED and target in PEGGED):
                continue
            series[(base, target)][day] = Decimal(rate)
            inverted[(target, base)][day] = 1 / Decimal(rate)
        for pair, by_day in inverted.items():
            for day, rate in by_day.items():
                series[pair].setdefault(day, rate)
        self._series = {}
        for pair, by_day in series.items():
            days = sorted(by_day)
            self._series[pair] = (days, [by_day[d] for d in days])

    @classmethod
    def load(cls):
        return cls(ExchangeRate.objects.values_list("base_currency", "target_currency", "rate", "date_extracted"))

    def _stored(self, base, target, on_date):
        """(rate, exact) from the stored series of one pair, or None. exact=False -> first rate is newer."""
        found = self._series.get((base, target))
        if not found:
            return None
        days, rates = found
        if on_date is None:
            return rates[-1], True
        index = bisect_right(days, on_date)
        if index:
            return rates[index - 1], True
        return rates[0], False

    def rate_day(self, base, target, on_date):
        """The day of the stored rate that ``lookup`` uses for a non-pegged pair, or None if there is none."""
        found = self._series.get((base, target))
        if not found:
            return None
        days = found[0]
        index = bisect_right(days, _as_date(on_date))
        return days[index - 1] if index else days[0]

    def lookup(self, base, target, on_date=None):
        """Return (rate as Decimal, exact). Raises MissingRate when the pair cannot be converted."""
        on_date = _as_date(on_date)
        if base == target:
            return Decimal(1), True
        # the peg: treat BGN as EUR scaled by a constant
        if base == "BGN":
            rate, exact = self.lookup("EUR", target, on_date)
            return rate / BGN_PER_EUR, exact
        if target == "BGN":
            rate, exact = self.lookup(base, "EUR", on_date)
            return rate * BGN_PER_EUR, exact

        found = self._stored(base, target, on_date)
        if found:
            return found
        if PIVOT not in (base, target):
            first = self._stored(base, PIVOT, on_date)
            second = self._stored(PIVOT, target, on_date)
            if first and second:
                return first[0] * second[0], first[1] and second[1]
        raise MissingRate(base, target)


# -- cached table --------------------------------------------------------------------------------
_cache = {"table": None, "loaded": 0.0}


def clear_cache(**kwargs):
    _cache["table"] = None


# loaded at most once per request: every new request starts with a fresh table
request_started.connect(clear_cache, dispatch_uid="currency_cache_request")
post_save.connect(clear_cache, sender=ExchangeRate, dispatch_uid="currency_cache_save")
post_delete.connect(clear_cache, sender=ExchangeRate, dispatch_uid="currency_cache_delete")


def get_table():
    if _cache["table"] is None or time.monotonic() - _cache["loaded"] > CACHE_SECONDS:
        _cache["table"] = RateTable.load()
        _cache["loaded"] = time.monotonic()
    return _cache["table"]


# -- public API ----------------------------------------------------------------------------------
def normalise_currency(value, default=DEFAULT_CURRENCY):
    """A valid currency code from user input; empty/unknown values fall back to ``default``."""
    from shopping.models import CurrencyChoice
    value = (value or "").strip().upper()
    return value if value in CurrencyChoice.values else default


def get_rate(base, target, on_date=None):
    """Rate that converts 1 ``base`` to ``target`` on ``on_date`` (latest when no date). Raises MissingRate."""
    return get_table().lookup(base, target, on_date)[0]


def convert(amount, base, target, on_date=None):
    """Convert one amount; returns a Decimal. Raises MissingRate."""
    return Decimal(str(amount)) * get_rate(base, target, on_date)


class ConversionReport:
    """What went wrong while converting a DataFrame: used for the warning banner on reports."""

    def __init__(self, target):
        self.target = target
        self.missing = Counter()       # currency -> rows that could not be converted (left out of totals)
        self.approximate = Counter()   # currency -> rows converted with a rate newer than the purchase

    def __bool__(self):
        return bool(self.missing or self.approximate)

    def messages(self):
        texts = []
        for currency, rows in sorted(self.missing.items()):
            texts.append(_("Липсва валутен курс %(base)s → %(target)s: %(rows)s записа не са включени в сумите.")
                         % {"base": currency, "target": self.target, "rows": rows})
        for currency, rows in sorted(self.approximate.items()):
            texts.append(_("Няма курс %(base)s → %(target)s към датата на %(rows)s записа: "
                           "използван е най-ранният наличен курс.")
                         % {"base": currency, "target": self.target, "rows": rows})
        return texts


def rate_factors(currencies, dates, target):
    """Per-row conversion factors for two aligned sequences (source currency, date).

    Returns (list of float | None, ConversionReport). None marks a row with no usable rate.
    One dictionary lookup per row; the rate itself is resolved once per distinct (currency, date).
    """
    table = get_table()
    report = ConversionReport(target)
    resolved = {}
    factors = []
    for key in zip(currencies, dates):
        if key not in resolved:
            try:
                rate, exact = table.lookup(key[0], target, key[1])
                resolved[key] = (float(rate), exact)
            except MissingRate:
                resolved[key] = (None, True)
        factor, exact = resolved[key]
        if factor is None:
            report.missing[key[0]] += 1
        elif not exact:
            report.approximate[key[0]] += 1
        factors.append(factor)
    return factors, report


def convert_df(df, target, currency_col, date_col, columns):
    """Add converted copies of ``columns`` ({source column: new column}) to ``df`` in ``target`` currency.

    Each row uses the rate of its own date. Rows without a rate get NaN (so they drop out of sums) and are
    counted in the returned ConversionReport. No database query per row.
    """
    import pandas as pd

    factors, report = rate_factors(df[currency_col].tolist(), df[date_col].tolist(), target)
    factor = pd.Series(factors, index=df.index, dtype="float64")
    for source, converted in columns.items():
        df[converted] = (df[source].astype(float) * factor).round(2)
    return report
