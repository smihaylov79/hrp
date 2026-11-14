from django.utils.translation import gettext as _

import pandas as pd

from .currency import ConversionReport, convert_df, normalise_currency


SHOPPING_FIELDS = [
    'amount',
    'price',
    'discount',
    'shopping__currency',
    'shopping__date',
    'shopping__shop__name',
    'product__name',
    'product__category__name',
    'product__category__main_category__name',
    'quantity',
    # ids for drill-down links, counting purchases and matching baskets
    'product_id',
    'product__category_id',
    'product__category__main_category_id',
    'shopping_id',
    'shopping__shop_id',
]
INCOME_FIELDS = ['amount', 'currency', 'date_received', 'income_type__name', 'user__first_name']
DERIVED_FIELDS = ['total', 'year', 'month', 'month_name', 'month_num']


def _add_period_columns(df, date_col):
    dates = pd.to_datetime(df[date_col])
    df['year'] = dates.dt.year
    df['month'] = dates.dt.strftime('%m.%Y')
    df['month_name'] = dates.dt.month_name()
    df['month_num'] = dates.dt.month
    return df


def db_to_df(db_shopping, currency):
    """Purchased products as a DataFrame with amounts and prices converted to ``currency``.

    Every purchase is converted with the rate of its own date (see reports/currency.py). Conversion problems
    are available as ``df.attrs['rates']`` (a ConversionReport) - show them with ``rate_warnings(df)``.
    An empty queryset gives an empty frame with the same columns.
    """
    currency = normalise_currency(currency)
    df = pd.DataFrame.from_records(db_shopping.values(*SHOPPING_FIELDS), columns=SHOPPING_FIELDS)
    if df.empty:
        df = pd.DataFrame(columns=SHOPPING_FIELDS + ['converted_amount', 'converted_price'] + DERIVED_FIELDS)
        df.attrs['rates'] = ConversionReport(currency)
        return df

    report = convert_df(df, currency, 'shopping__currency', 'shopping__date',
                        {'amount': 'converted_amount', 'price': 'converted_price'})
    # products without (main) category or shop must stay visible in every grouping
    df['product__category__name'] = df['product__category__name'].fillna(_('Без категория'))
    df['product__category__main_category__name'] = (
        df['product__category__main_category__name'].fillna(_('Без категория')))
    df['shopping__shop__name'] = df['shopping__shop__name'].fillna(_('Без магазин'))

    df = df.sort_values(by='shopping__date', ascending=True)
    df['total'] = df['converted_amount']
    df = _add_period_columns(df, 'shopping__date')
    df.attrs['rates'] = report
    return df


def income_db_to_df(db_income, currency):
    """Incomes as a DataFrame converted to ``currency`` with the rate of the day they were received."""
    currency = normalise_currency(currency)
    df = pd.DataFrame.from_records(db_income.values(*INCOME_FIELDS), columns=INCOME_FIELDS)
    if df.empty:
        df = pd.DataFrame(columns=INCOME_FIELDS + ['converted_amount'] + DERIVED_FIELDS)
        df.attrs['rates'] = ConversionReport(currency)
        return df

    report = convert_df(df, currency, 'currency', 'date_received', {'amount': 'converted_amount'})
    df = df.sort_values(by='date_received', ascending=True)
    df['total'] = df['converted_amount'].astype(float)
    df = _add_period_columns(df, 'date_received')
    df.attrs['rates'] = report
    return df


def rate_warnings(*frames):
    """Texts for the "rates missing" banner, collected from DataFrames made by db_to_df / income_db_to_df."""
    texts = []
    for frame in frames:
        report = getattr(frame, 'attrs', {}).get('rates') if frame is not None else None
        if report:
            texts.extend(text for text in report.messages() if text not in texts)
    return texts
