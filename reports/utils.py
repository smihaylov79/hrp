from dateutil.relativedelta import relativedelta
from django.db.models import Sum, F
from django.shortcuts import get_object_or_404

from shopping.models import Product, ShoppingProduct
from users.models import CustomUser
from django.utils.translation import gettext as _

from .currency import ConversionReport, convert_df, normalise_currency
import pandas as pd
from calendar import month_name


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



def calculate_price_changes(df):
    df['shopping__date'] = pd.to_datetime(df['shopping__date'])
    df_sorted = df.sort_values(by=['product__name', 'shopping__date'])
    price_changes = df_sorted.groupby('product__name').agg(
        first_price=('converted_price', lambda x: x.iloc[0]),
        last_price=('converted_price', lambda x: x.iloc[-1])
    )
    price_changes['change'] = price_changes['last_price'] - price_changes['first_price']
    biggest_increase = price_changes.sort_values(by='change', ascending=False).iloc[0].to_dict()
    biggest_decrease = price_changes.sort_values(by='change').iloc[0].to_dict()

    biggest_increase['product'] = price_changes.sort_values(by='change', ascending=False).index[0]
    biggest_decrease['product'] = price_changes.sort_values(by='change').index[0]
    for key in ['first_price', 'last_price', 'change']:
        biggest_increase[key] = round(biggest_increase[key], 2)
        biggest_decrease[key] = round(biggest_decrease[key], 2)
    return biggest_increase, biggest_decrease


def monthly_compare_chart(df):
    month_order = list(month_name)[1:]
    month_labels = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
                    'October', 'November', 'December']

    highcharts_series = []
    for year in df['year'].unique():
        year_df = df[df['year'] == year]
        monthly_totals = (
            year_df.groupby('month_name')['total']
            .sum()
            .reindex(month_order, fill_value=0)
        )

        highcharts_series.append({
            'name': str(year),
            'data': [round(monthly_totals[m], 2) if monthly_totals[m] != 0 else None for m in month_order],
        })

    return highcharts_series, month_labels


def monthly_weekly_spending(df):
    monthly_spent = df.groupby(['year', 'month_num', 'month'])['total'].sum().reset_index().sort_values(
        by='year').to_dict(orient='records')
    df['week'] = pd.to_datetime(df['shopping__date']).dt.isocalendar().week
    weekly_spent = (
        df.groupby(['year', 'week'])['total'].sum().reset_index().sort_values(by='year').to_dict(orient='records')
    )
    return monthly_spent, weekly_spent


def by_category_spending(df):
    main_category_spending = (df.groupby('product__category__main_category__name')['total'].sum().reset_index()
                              .rename(columns={'product__category__main_category__name': 'name', 'total': 'y'})
                              .sort_values(by='y', ascending=False)
                              .to_dict(orient='records'))

    subcategory_spending = (
        df.groupby('product__category__name')['converted_amount']
        .sum()
        .reset_index()
        .rename(columns={'product__category__name': 'name', 'converted_amount': 'y'})
        .sort_values(by='y', ascending=False)
        .to_dict(orient='records')
    )
    return main_category_spending, subcategory_spending


def by_product_statistics(df):
    biggest_spent = df.groupby('product__name')['total'].sum().reset_index().sort_values(by='total', ascending=False).iloc[0].to_dict()
    biggest_spent['spent'] = biggest_spent.pop('total')

    # compare prices in the report currency, not in the currency each purchase happened to be made in
    priced = df[df['converted_price'] > 0]
    lowest_price = (priced if not priced.empty else df).sort_values(by='converted_price', ascending=True).iloc[0].to_dict()
    lowest_price['price'] = lowest_price['converted_price']
    highest_price = df.sort_values(by='converted_price', ascending=False).iloc[0].to_dict()
    highest_price['price'] = highest_price['converted_price']
    return biggest_spent, lowest_price, highest_price


def calculate_inflation(data):
    df = pd.DataFrame(data)

    df['prev_total'] = df['total'].shift(1)
    df['inflation_mom'] = ((df['total'] - df['prev_total']) / df['prev_total']) * 100
    df['inflation_mom'] = df['inflation_mom'].round(2)
    return df


def product_price_history(request):
    user = request.user
    household = user.household

    if household:
        members = CustomUser.objects.filter(household=household)
        products = Product.objects.filter(
            shoppingproduct__shopping__user__in=members).order_by('name').distinct()
    else:
        products = Product.objects.filter(
            shoppingproduct__shopping__user=user).distinct().order_by('name').distinct()

    selected_product_id = request.GET.get("product")
    currency = normalise_currency(request.GET.get("currency"))
    price_data_json = []

    if selected_product_id:
        product = get_object_or_404(Product, id=selected_product_id)

        if household:
            price_changes = ShoppingProduct.objects.filter(shopping__user__in=members, product=product)
        else:
            price_changes = ShoppingProduct.objects.filter(shopping__user=user, product=product)

        if price_changes.exists():
            price_data = db_to_df(price_changes, currency)

            minimal_df = pd.DataFrame({
                'date': pd.to_datetime(price_data['shopping__date'], errors='coerce').dt.strftime('%Y-%m-%d'),
                'price': price_data['converted_price'].astype(float)
            })

            price_data_json = minimal_df.to_dict(orient='records')

    return products, selected_product_id, price_data_json, currency


def income_vs_spendings(income_qs, spendings_qs, currency):
    # конверсия към DataFrame
    df_income = income_db_to_df(income_qs, currency)
    df_spendings = db_to_df(spendings_qs, currency)

    # групиране по месец
    income_monthly = df_income.groupby("month")["total"].sum().reset_index()
    spendings_monthly = df_spendings.groupby("month")["total"].sum().reset_index()
    # merge
    comparison = pd.merge(income_monthly, spendings_monthly, on="month", how="outer", suffixes=("_income", "_spendings")).fillna(0)

    # нетен баланс
    comparison["net_balance"] = comparison["total_income"] - comparison["total_spendings"]
    return comparison, rate_warnings(df_income, df_spendings)


def get_category_totals(start_date, end_date):
    return (
        ShoppingProduct.objects
        .filter(shopping__date__range=(start_date, end_date),
                not_for_household=False)
        .values(main_category=F("product__category__main_category__name"))
        .annotate(total=Sum("amount"))
        .order_by("main_category")
    )


def get_same_month_previous_years(start_date, years_back=3):
    periods = []
    for i in range(1, years_back + 1):
        prev_start = start_date - relativedelta(years=i)
        prev_end = prev_start.replace(day=1) + relativedelta(months=1) - relativedelta(days=1)
        periods.append((prev_start, prev_end))
    return periods