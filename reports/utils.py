from django.shortcuts import get_object_or_404

from shopping.models import Product, ShoppingProduct
from users.models import CustomUser
from .models import ExchangeRate
import pandas as pd
from calendar import month_name


def convert_amount(row, target_currency):
    base = row['shopping__currency']
    rate = ExchangeRate.objects.filter(base_currency=base, target_currency=target_currency).order_by('-date_extracted').values_list('rate', flat=True).first()
    rate = float(rate or 1.0)
    return {
        'converted_amount': float(row['amount']) * rate,
        'converted_price': float(row['price']) * rate
    }


def db_to_df(db_shopping, currency):
    df = pd.DataFrame.from_records(db_shopping.values(
        'amount',
        'price',
        'discount',
        'shopping__currency',
        'shopping__date',
        'shopping__shop__name',
        'product__name',
        'product__category__name',
        'product__category__main_category__name',
    )
    )
    df_converted = df.apply(lambda row: convert_amount(row, currency), axis=1, result_type='expand')
    df['converted_amount'] = df_converted['converted_amount'].round(2)
    df['converted_price'] = df_converted['converted_price'].round(2)
    df = df.sort_values(by='shopping__date', ascending=True)
    df['total'] = df['converted_amount']
    df['year'] = pd.to_datetime(df['shopping__date']).dt.year
    df['month'] = pd.to_datetime(df['shopping__date']).dt.strftime('%m.%Y')
    df['month_name'] = pd.to_datetime(df['shopping__date']).dt.month_name()
    df['month_num'] = pd.to_datetime(df['shopping__date']).dt.month
    return df


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

    lowest_price = df[df['price'] > 0].sort_values(by='price', ascending=True).iloc[0].to_dict()
    lowest_price['price'] = lowest_price['converted_price']
    highest_price = df.sort_values(by='price', ascending=False).iloc[0].to_dict()
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
            shoppingproduct__shopping__user__in=members).distinct()
    else:
        products = Product.objects.filter(
            shoppingproduct__shopping__user=user).distinct()

    selected_product_id = request.GET.get("product")
    currency = request.GET.get("currency")
    price_data_json = []

    if selected_product_id:
        product = get_object_or_404(Product, id=selected_product_id)

        if household:
            price_changes = ShoppingProduct.objects.filter(shopping__user__in=members, product=product)
        else:
            price_changes = ShoppingProduct.objects.filter(shopping__user=user, product=product)

        price_data = price_changes.select_related('shopping', 'shop', 'product__category__main_category')
        price_data = db_to_df(price_data, currency)

        minimal_df = pd.DataFrame({
            'date': pd.to_datetime(price_data['shopping__date'], errors='coerce').dt.strftime('%Y-%m-%d'),
            'price': price_data['converted_price'].astype(float)
        })

        price_data_json = minimal_df.to_dict(orient='records')

    return products, selected_product_id, price_data_json, currency

