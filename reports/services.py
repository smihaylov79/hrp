"""Data for the six tabs of the Reports hub.

Every function takes the logged-in user and a ReportFilters object and returns plain dicts / Table objects.
All data is scoped to the user (or their household) and converted with reports/currency.py.
"""
from dateutil.relativedelta import relativedelta
from django.utils.translation import gettext as _

import pandas as pd

from budget.models import Budget, BudgetIncomeItem, BudgetItem
from income.models import Income
from shopping.models import ShoppingProduct
from users.models import CustomUser

from .currency import MissingRate, get_rate
from .export import INTEGER, MONEY, NUMBER, PERCENT, TEXT, Table
from .models import HouseholdInflationBasket, UserInflationBasket
from .utils import db_to_df, income_db_to_df, rate_warnings

MAIN = 'product__category__main_category__name'
MAIN_ID = 'product__category__main_category_id'
SUB = 'product__category__name'
SUB_ID = 'product__category_id'
SHOP = 'shopping__shop__name'
SHOP_ID = 'shopping__shop_id'


# ------------------------------------------------------------------------------------------------
# scoping and loading
# ------------------------------------------------------------------------------------------------
def scoped_purchases(user, scope='all'):
    """Purchased products the user may see, narrowed by the scope filter."""
    if user.household_id:
        members = CustomUser.objects.filter(household_id=user.household_id)
        purchases = ShoppingProduct.objects.filter(shopping__user__in=members)
    else:
        purchases = ShoppingProduct.objects.filter(shopping__user=user)
    if scope == 'household':
        purchases = purchases.filter(not_for_household=False)
    elif scope == 'external':
        purchases = purchases.filter(not_for_household=True)
    elif scope == 'mine':
        purchases = purchases.filter(shopping__user=user)
    return purchases


def scoped_incomes(user, scope='all'):
    if user.household_id and scope != 'mine':
        return Income.objects.filter(user__household_id=user.household_id)
    return Income.objects.filter(user=user)


def load_spending(user, filters, start, end):
    df = db_to_df(scoped_purchases(user, filters.scope).filter(shopping__date__range=(start, end)), filters.currency)
    df['date'] = pd.to_datetime(df['shopping__date'])
    df['quantity'] = df['quantity'].astype(float)
    return df


def load_income(user, filters, start, end):
    df = income_db_to_df(scoped_incomes(user, filters.scope).filter(date_received__range=(start, end)),
                         filters.currency)
    df['date'] = pd.to_datetime(df['date_received'])
    return df


def between(df, start, end):
    return df[(df['date'] >= pd.Timestamp(start)) & (df['date'] <= pd.Timestamp(end))]


def total(df):
    return round(float(df['total'].sum()), 2) if not df.empty else 0.0


def percent_change(current, previous):
    """Change in percent, or None when there is nothing to compare with."""
    if not previous:
        return None
    return round((current - previous) / abs(previous) * 100, 1)


def share(part, whole):
    return round(part / whole * 100, 1) if whole else 0.0


def month_starts(start, end):
    first = start.replace(day=1)
    months = []
    while first <= end:
        months.append(first)
        first = first + relativedelta(months=1)
    return months


def month_label(month):
    return f'{month:%m.%y}'       # short and the same width in every language, e.g. 11.26


def monthly_totals(df, months):
    """Sum of ``total`` per calendar month, aligned to ``months`` (missing months are 0)."""
    if df.empty:
        return [0.0] * len(months)
    by_month = df.groupby(df['date'].dt.to_period('M'))['total'].sum()
    return [round(float(by_month.get(pd.Period(month, 'M'), 0.0)), 2) for month in months]


def sparkline(values, width=96, height=28, pad=5):
    """SVG path + last point for a tiny trend line (no axes; the numbers are in the card and the table)."""
    if len(values) < 2 or max(values) == min(values):
        return None
    low, high = min(values), max(values)
    step = (width - 2 * pad) / (len(values) - 1)
    points = [(pad + index * step, height - pad - (value - low) / (high - low) * (height - 2 * pad))
              for index, value in enumerate(values)]
    return {
        'path': 'M' + ' L'.join(f'{x:.1f},{y:.1f}' for x, y in points),
        'x': f'{points[-1][0]:.1f}', 'y': f'{points[-1][1]:.1f}',
        'viewbox': f'0 0 {width} {height}',
    }


# ------------------------------------------------------------------------------------------------
# budget against actual spending
# ------------------------------------------------------------------------------------------------
def current_budget(user, start, end):
    """The newest submitted budget of the user's household (or of the user) that overlaps the period."""
    if user.household_id:
        budgets = Budget.objects.filter(household_id=user.household_id)
    else:
        budgets = Budget.objects.filter(creator=user, household__isnull=True)
    return budgets.filter(submitted=True, date_from__lte=end, date_to__gte=start).order_by('-date_from').first()


def budget_vs_actual(user, filters, spending, income=None):
    """Planned (the part of the budget that falls inside the period) against actual, per main category."""
    budget = current_budget(user, filters.start, filters.end)
    if budget is None:
        return None
    try:
        rate = float(get_rate(budget.currency, filters.currency))
    except MissingRate:
        return None
    overlap_days = (min(filters.end, budget.date_to) - max(filters.start, budget.date_from)).days + 1
    budget_days = (budget.date_to - budget.date_from).days + 1
    part = overlap_days / budget_days

    actual = spending.groupby(MAIN)['total'].sum().to_dict() if not spending.empty else {}
    rows = []
    for item in BudgetItem.objects.filter(budget=budget).select_related('category'):
        planned = float(item.planned_amount) * part * rate
        spent = float(actual.pop(item.category.name, 0.0))
        rows.append({'category': item.category.name, 'planned': round(planned, 2), 'actual': round(spent, 2)})
    for name, spent in actual.items():       # spending in categories the budget does not plan for
        rows.append({'category': name, 'planned': 0.0, 'actual': round(float(spent), 2)})
    for row in rows:
        row['variance'] = round(row['actual'] - row['planned'], 2)
        row['percent'] = round(row['actual'] / row['planned'] * 100, 1) if row['planned'] else None
        row['over'] = row['actual'] > row['planned']
        row['width'] = min(round(row['percent']), 100) if row['percent'] is not None else 100
    rows.sort(key=lambda row: row['planned'], reverse=True)

    planned_total = round(sum(row['planned'] for row in rows), 2)
    actual_total = round(sum(row['actual'] for row in rows), 2)
    result = {
        'budget': budget,
        'rows': rows,
        'planned': planned_total,
        'actual': actual_total,
        'variance': round(actual_total - planned_total, 2),
        'percent': round(actual_total / planned_total * 100) if planned_total else None,
    }
    if income is not None:
        planned_income = sum(float(item.planned_amount) for item in BudgetIncomeItem.objects.filter(budget=budget))
        result['planned_income'] = round(planned_income * part * rate, 2)
        result['actual_income'] = total(income)
    return result


# ------------------------------------------------------------------------------------------------
# 1. Overview
# ------------------------------------------------------------------------------------------------
def overview(user, filters):
    previous_start, previous_end = filters.previous
    year_start, year_end = filters.last_year
    chart_months = month_starts(filters.end.replace(day=1) - relativedelta(months=11), filters.end)
    load_from = min(chart_months[0], previous_start, year_start, filters.start)

    spending_all = load_spending(user, filters, load_from, filters.end)
    income_all = load_income(user, filters, load_from, filters.end)
    spending = between(spending_all, filters.start, filters.end)
    income = between(income_all, filters.start, filters.end)

    spent = total(spending)
    spent_previous = total(between(spending_all, previous_start, previous_end))
    spent_last_year = total(between(spending_all, year_start, year_end))
    earned = total(income)
    earned_previous = total(between(income_all, previous_start, previous_end))
    net = round(earned - spent, 2)

    spend_series = monthly_totals(spending_all, chart_months)
    income_series = monthly_totals(income_all, chart_months)
    earned_12 = sum(income_series)
    daily = spending.groupby('date')['total'].sum() if not spending.empty else pd.Series(dtype=float)

    by_category = (spending.groupby(MAIN)['total'].sum().sort_values(ascending=False)
                   if not spending.empty else pd.Series(dtype=float))
    top = [{'name': name, 'value': round(float(value), 2), 'share': share(float(value), spent),
            'width': share(float(value), float(by_category.iloc[0]))} for name, value in by_category.head(5).items()]
    rest = round(spent - sum(row['value'] for row in top), 2)

    largest = spending.sort_values('converted_amount', ascending=False).head(8) if not spending.empty else spending
    largest_table = Table('largest_purchases', _('Най-големи покупки'), [
        ('product', _('Продукт'), TEXT), ('shop', _('Магазин'), TEXT), ('date', _('Дата'), TEXT),
        ('amount', _('Сума'), MONEY),
    ], [{'product': row['product__name'], 'shop': row[SHOP], 'date': row['shopping__date'].strftime('%d.%m.%Y'),
         'amount': row['converted_amount']} for _index, row in largest.iterrows()])

    months_table = Table('income_and_spending_by_month', _('Приходи и разходи по месеци'), [
        ('month', _('Месец'), TEXT), ('income', _('Приходи'), MONEY), ('spending', _('Разходи'), MONEY),
        ('net', _('Нетно'), MONEY),
    ], [{'month': month_label(month), 'income': earned_month, 'spending': spent_month,
         'net': round(earned_month - spent_month, 2)}
        for month, earned_month, spent_month in zip(chart_months, income_series, spend_series)])

    budget = budget_vs_actual(user, filters, spending)
    return {
        'kpi': {
            'spent': spent,
            'purchases': int(spending['shopping_id'].nunique()) if not spending.empty else 0,
            'per_day': round(spent / filters.days, 2),
            'previous': spent_previous,
            'previous_diff': round(spent - spent_previous, 2),
            'previous_pct': percent_change(spent, spent_previous),
            'last_year': spent_last_year,
            'last_year_diff': round(spent - spent_last_year, 2),
            'last_year_pct': percent_change(spent, spent_last_year),
            'income': earned,
            'income_pct': percent_change(earned, earned_previous),
            'net': net,
            'savings_rate': round(net / earned * 100, 1) if earned else None,
            'savings_rate_12': round((earned_12 - sum(spend_series)) / earned_12 * 100, 1) if earned_12 else None,
            'top_day': ({'date': daily.idxmax().strftime('%d.%m'), 'amount': round(float(daily.max()), 2)}
                        if not daily.empty else None),
            'spark_spending': sparkline(spend_series),
            'spark_income': sparkline(income_series),
        },
        'chart': {'months': [month_label(month) for month in chart_months],
                  'income': income_series, 'spending': spend_series},
        'top_categories': top,
        'other_categories': {'value': rest, 'share': share(rest, spent), 'count': max(len(by_category) - len(top), 0)},
        'budget': budget,
        'tables': {table.key: table for table in (months_table, largest_table)},
        'months_table': months_table,
        'largest_table': largest_table,
        'has_data': bool(spent or earned),
        'warnings': rate_warnings(spending_all, income_all),
    }


# ------------------------------------------------------------------------------------------------
# 2. Categories (drill-down main -> sub -> products, year-over-year)
# ------------------------------------------------------------------------------------------------
def categories(user, filters, main_id=None, sub_id=None):
    year_start, year_end = filters.last_year
    spending = load_spending(user, filters, filters.start, filters.end)
    last_year = load_spending(user, filters, year_start, year_end)

    main_name = sub_name = None
    if main_id:
        selected = spending[spending[MAIN_ID] == main_id]
        main_name = (selected[MAIN].iloc[0] if not selected.empty
                     else (last_year[last_year[MAIN_ID] == main_id][MAIN].iloc[0]
                           if not last_year[last_year[MAIN_ID] == main_id].empty else None))
        spending, last_year = selected, last_year[last_year[MAIN_ID] == main_id]
    if sub_id:
        selected = spending[spending[SUB_ID] == sub_id]
        sub_name = selected[SUB].iloc[0] if not selected.empty else None
        spending, last_year = selected, last_year[last_year[SUB_ID] == sub_id]

    # level shown in the bars and in the year-over-year table
    if sub_id:
        name_col, id_col, param = 'product__name', 'product_id', None
    elif main_id:
        name_col, id_col, param = SUB, SUB_ID, 'sub'
    else:
        name_col, id_col, param = MAIN, MAIN_ID, 'main'

    spent = total(spending)
    current = (spending.groupby([id_col, name_col], dropna=False)['total'].sum().reset_index()
               .sort_values('total', ascending=False) if not spending.empty else pd.DataFrame(columns=[id_col, name_col, 'total']))
    top_value = float(current['total'].iloc[0]) if not current.empty else 0
    bars = []
    for _index, row in current.head(15).iterrows():
        value = float(row['total'])
        target = None
        if param and not pd.isna(row[id_col]):
            target = filters.query(**({'main': main_id, 'sub': int(row[id_col])} if param == 'sub'
                                      else {'main': int(row[id_col])}))
        bars.append({'name': row[name_col], 'value': round(value, 2), 'share': share(value, spent),
                     'width': share(value, top_value), 'query': target})

    before = last_year.groupby(name_col)['total'].sum().to_dict() if not last_year.empty else {}
    now = current.set_index(name_col)['total'].to_dict()
    yoy_rows = []
    for name in sorted(set(now) | set(before), key=lambda key: -(now.get(key, 0))):
        this_year, that_year = float(now.get(name, 0)), float(before.get(name, 0))
        yoy_rows.append({'name': name, 'current': round(this_year, 2), 'previous': round(that_year, 2),
                         'diff': round(this_year - that_year, 2), 'pct': percent_change(this_year, that_year)})
    spent_before = total(last_year)
    yoy_table = Table('year_over_year', _('Спрямо същия период на предходната година'), [
        ('name', _('Категория') if not sub_id else _('Продукт'), TEXT),
        ('current', _('Избран период'), MONEY), ('previous', _('Година по-рано'), MONEY),
        ('diff', _('Разлика'), MONEY), ('pct', _('Промяна'), PERCENT),
    ], yoy_rows, total={'name': _('Общо'), 'current': spent, 'previous': spent_before,
                        'diff': round(spent - spent_before, 2), 'pct': percent_change(spent, spent_before)})

    if spending.empty:
        product_rows = []
    else:
        grouped = spending.groupby(['product_id', 'product__name', SUB]).agg(
            quantity=('quantity', 'sum'), spent=('total', 'sum'), times=('shopping_id', 'nunique')).reset_index()
        grouped = grouped.sort_values('spent', ascending=False)
        product_rows = [{'product': row['product__name'], 'category': row[SUB], 'quantity': row['quantity'],
                         'times': row['times'], 'spent': round(float(row['spent']), 2),
                         'unit_price': round(float(row['spent']) / row['quantity'], 2) if row['quantity'] else None}
                        for _index, row in grouped.iterrows()]
    products_table = Table('products', _('Продукти'), [
        ('product', _('Продукт'), TEXT), ('category', _('Категория'), TEXT), ('quantity', _('Количество'), NUMBER),
        ('times', _('Покупки'), INTEGER), ('unit_price', _('Средна цена'), MONEY), ('spent', _('Сума'), MONEY),
    ], product_rows, limit=100)

    return {
        'spent': spent,
        'per_day': round(spent / filters.days, 2),
        'bars': bars,
        'bars_hidden': max(len(current) - len(bars), 0),
        'level': 'products' if sub_id else ('sub' if main_id else 'main'),
        'main_id': main_id, 'main_name': main_name, 'sub_id': sub_id, 'sub_name': sub_name,
        'yoy_table': yoy_table,
        'products_table': products_table,
        'tables': {table.key: table for table in (yoy_table, products_table)},
        'warnings': rate_warnings(spending, last_year),
    }


# ------------------------------------------------------------------------------------------------
# 3. Shops
# ------------------------------------------------------------------------------------------------
def shops(user, filters, shop_ids=()):
    everything = load_spending(user, filters, filters.start, filters.end)
    shop_choices = ([] if everything.empty else
                    [{'id': int(shop_id), 'name': name, 'selected': int(shop_id) in shop_ids}
                     for (shop_id, name), _rows in everything.dropna(subset=[SHOP_ID]).groupby([SHOP_ID, SHOP])])
    shop_choices.sort(key=lambda shop: shop['name'].lower())
    spending = everything[everything[SHOP_ID].isin(shop_ids)] if shop_ids else everything
    spent = total(spending)

    if spending.empty:
        by_shop = pd.DataFrame(columns=[SHOP, 'spent', 'purchases'])
    else:
        by_shop = (spending.groupby(SHOP).agg(spent=('total', 'sum'), purchases=('shopping_id', 'nunique'))
                   .reset_index().sort_values('spent', ascending=False))
    top_value = float(by_shop['spent'].iloc[0]) if not by_shop.empty else 0
    shop_rows = [{'shop': row[SHOP], 'spent': round(float(row['spent']), 2), 'purchases': int(row['purchases']),
                  'average': round(float(row['spent']) / row['purchases'], 2) if row['purchases'] else None,
                  'share': share(float(row['spent']), spent), 'width': share(float(row['spent']), top_value)}
                 for _index, row in by_shop.iterrows()]
    shops_table = Table('shops', _('Магазини'), [
        ('shop', _('Магазин'), TEXT), ('purchases', _('Покупки'), INTEGER),
        ('average', _('Средно на покупка'), MONEY), ('spent', _('Сума'), MONEY), ('share', _('Дял'), PERCENT),
    ], shop_rows)

    # price of the same product in different shops (unit price = amount / quantity, so discounts count)
    comparison_rows, comparison_columns, basket = [], [('product', _('Продукт'), TEXT)], []
    priced = spending[spending['quantity'] > 0].copy()
    if not priced.empty:
        priced['unit'] = priced['converted_amount'] / priced['quantity']
        compare_shops = list(by_shop[SHOP].head(6))
        priced = priced[priced[SHOP].isin(compare_shops)]
        prices = priced.groupby(['product__name', SHOP])['unit'].mean().unstack(SHOP)
        prices = prices[prices.notna().sum(axis=1) >= 2]
        if not prices.empty:
            order = priced.groupby('product__name')['total'].sum().reindex(prices.index).sort_values(ascending=False)
            prices = prices.loc[order.index]
            compare_shops = [name for name in compare_shops if name in prices.columns]
            comparison_columns += [(name, name, MONEY) for name in compare_shops]
            for product, row in prices.iterrows():
                values = {name: round(float(row[name]), 2) for name in compare_shops if not pd.isna(row[name])}
                cheapest = min(values.values())
                comparison_rows.append({'product': product, **values,
                                        'highlight': [name for name, value in values.items() if value == cheapest]})

            # the same basket in the 3 biggest shops: only products that were bought in all of them
            basket_shops = compare_shops[:3]
            common = prices[basket_shops].dropna()
            if len(basket_shops) >= 2 and not common.empty:
                typical = priced.groupby('product__name')['quantity'].median().reindex(common.index)
                costs = {name: round(float((common[name] * typical).sum()), 2) for name in basket_shops}
                cheapest = min(costs.values())
                basket = {'products': len(common),
                          'shops': [{'shop': name, 'cost': cost, 'cheapest': cost == cheapest,
                                     'extra': round(cost - cheapest, 2)} for name, cost in costs.items()]}
    comparison_table = Table('price_comparison', _('Цени по магазини'), comparison_columns, comparison_rows, limit=40)

    return {
        'spent': spent,
        'shop_rows': shop_rows[:12],
        'shop_choices': shop_choices,
        'selected_shops': list(shop_ids),
        'shops_table': shops_table,
        'comparison_table': comparison_table,
        'basket': basket,
        'tables': {table.key: table for table in (shops_table, comparison_table)},
        'warnings': rate_warnings(everything),
    }


# ------------------------------------------------------------------------------------------------
# 4. Prices and personal inflation
# ------------------------------------------------------------------------------------------------
def basket_index(df):
    """Laspeyres price index of a set of products: a fixed basket priced month by month, first month = 100.

    * quantity of each product: its average monthly quantity over the whole period (fixed for all months)
    * price of a product in a month: the median unit price paid (amount / quantity, so discounts count);
      a month without a purchase keeps the last known price, months before the first purchase use the first
    Buying more or less of something therefore does not move the index - only prices do.
    Returns None when there are fewer than two months of data.
    """
    data = df[df['quantity'] > 0]
    if data.empty:
        return None
    data = data.assign(unit=data['converted_amount'] / data['quantity'], month=data['date'].dt.to_period('M'))
    months = pd.period_range(data['month'].min(), data['month'].max(), freq='M')
    if len(months) < 2:
        return None
    prices = data.groupby(['product_id', 'month'])['unit'].median().unstack('month').reindex(columns=months)
    prices = prices.ffill(axis=1).bfill(axis=1)
    quantities = data.groupby('product_id')['quantity'].sum() / len(months)
    cost = prices.mul(quantities, axis=0).sum(axis=0)
    if not cost.iloc[0]:
        return None
    index = (cost / cost.iloc[0] * 100).round(1)
    return {
        'months': [month_label(month.to_timestamp().date()) for month in months],
        'values': [float(value) for value in index],
        'change': round(float(index.iloc[-1]) - 100, 1),
        'products': int(len(prices)),
    }


STABLE_PRICE_RATIO = 3      # highest / lowest monthly price above this = not a comparable unit price


def regular_products(priced):
    """Products for the automatic basket: bought in at least 3 different months and with a stable unit price.

    Many "products" are not goods with a unit price (gifts, rent, trips, investments): the amount paid differs
    every time, which would look like wild price changes. They are left out; a user basket can still include
    anything.
    """
    data = priced.assign(unit=priced['converted_amount'] / priced['quantity'], month=priced['date'].dt.to_period('M'))
    monthly = data[data['unit'] > 0].groupby(['product_id', 'month'])['unit'].median()
    stats = monthly.groupby('product_id').agg(['count', 'min', 'max'])
    stable = stats[(stats['count'] >= 3) & (stats['max'] <= stats['min'] * STABLE_PRICE_RATIO)]
    return set(stable.index)


def user_baskets(user):
    """[(basket, set of product ids)] for the baskets of the user's household, or of the user."""
    if user.household_id:
        baskets = HouseholdInflationBasket.objects.filter(household_id=user.household_id).prefetch_related(
            'household_basket_items__product')
        return [(basket, {item.product.product_id for item in basket.household_basket_items.all()})
                for basket in baskets.order_by('name')]
    baskets = UserInflationBasket.objects.filter(user=user).prefetch_related('user_basket_items__product')
    return [(basket, {item.product.product_id for item in basket.user_basket_items.all()})
            for basket in baskets.order_by('name')]


def prices(user, filters, product_id=None):
    spending = load_spending(user, filters, filters.start, filters.end)
    priced = spending[spending['quantity'] > 0]

    indexes = []
    if not priced.empty:
        regular = regular_products(priced)
        everything = basket_index(priced[priced['product_id'].isin(regular)]) if regular else None
        if everything:
            indexes.append({'key': 'regular', 'name': _('Редовно купувани продукти'), 'basket_id': None,
                            'hint': _('Купувани в поне 3 месеца, с устойчива единична цена'), **everything})
    for basket, product_ids in user_baskets(user):
        result = basket_index(priced[priced['product_id'].isin(product_ids)]) if product_ids else None
        indexes.append({'key': f'basket-{basket.pk}', 'name': basket.name, 'basket_id': basket.pk,
                        'hint': _('Ваша кошница'), **(result or {'months': [], 'values': [], 'change': None,
                                                                  'products': 0})})

    # first against last unit price of every product bought on at least two days
    change_rows = []
    if not priced.empty:
        ordered = priced.assign(unit=priced['converted_amount'] / priced['quantity']).sort_values('date')
        for (product, name), rows in ordered.groupby(['product_id', 'product__name']):
            if rows['date'].nunique() < 2:
                continue
            first, last = float(rows['unit'].iloc[0]), float(rows['unit'].iloc[-1])
            if first <= 0:
                continue
            change_rows.append({'product': name, 'first': round(first, 2), 'last': round(last, 2),
                                'diff': round(last - first, 2), 'pct': round((last - first) / first * 100, 1),
                                'url': filters.query(product=int(product)) + '#history'})
        change_rows.sort(key=lambda row: row['pct'], reverse=True)
    comparable = [row for row in change_rows if row['last'] and 1 / STABLE_PRICE_RATIO <= row['last'] / row['first'] <= STABLE_PRICE_RATIO]
    changes_table = Table('price_changes', _('Промяна на цените'), [
        ('product', _('Продукт'), TEXT), ('first', _('Първа цена'), MONEY), ('last', _('Последна цена'), MONEY),
        ('diff', _('Разлика'), MONEY), ('pct', _('Промяна'), PERCENT),
    ], change_rows, limit=40)

    products = ([] if spending.empty else
                [{'id': int(pid), 'name': name, 'selected': int(pid) == product_id}
                 for (pid, name), _rows in spending.groupby(['product_id', 'product__name'])])
    products.sort(key=lambda row: row['name'].lower())
    history = None
    if product_id:
        rows = priced[priced['product_id'] == product_id].sort_values('date')
        if not rows.empty:
            unit = (rows['converted_amount'] / rows['quantity']).round(2)
            history = {
                'name': rows['product__name'].iloc[0],
                'points': [{'date': day.strftime('%Y-%m-%d'), 'label': day.strftime('%d.%m.%Y'), 'price': float(price),
                            'shop': shop} for day, price, shop in zip(rows['date'], unit, rows[SHOP])],
                'low': float(unit.min()), 'high': float(unit.max()), 'last': float(unit.iloc[-1]),
            }
    history_table = Table('price_history', _('Движение на цената'), [
        ('label', _('Дата'), TEXT), ('shop', _('Магазин'), TEXT), ('price', _('Единична цена'), MONEY),
    ], history['points'] if history else [], limit=60)

    return {
        'indexes': indexes,
        'changes_table': changes_table,
        # the short lists skip jumps of more than 3x: that is a different thing bought, not a price change
        'increases': [row for row in comparable if row['pct'] > 0][:5],
        'decreases': [row for row in reversed(comparable) if row['pct'] < 0][:5],
        'products': products,
        'history': history,
        'history_table': history_table,
        'tables': {table.key: table for table in (changes_table, history_table)},
        'warnings': rate_warnings(spending),
    }


# ------------------------------------------------------------------------------------------------
# 5. Cash flow
# ------------------------------------------------------------------------------------------------
def cash_flow(user, filters):
    spending = load_spending(user, filters, filters.start, filters.end)
    income = load_income(user, filters, filters.start, filters.end)
    months = month_starts(filters.start, filters.end)
    earned, spent = monthly_totals(income, months), monthly_totals(spending, months)

    rows, running = [], 0.0
    for month, earned_month, spent_month in zip(months, earned, spent):
        net = round(earned_month - spent_month, 2)
        running = round(running + net, 2)
        rows.append({'month': month_label(month), 'income': earned_month, 'spending': spent_month, 'net': net,
                     'cumulative': running,
                     'savings_rate': round(net / earned_month * 100, 1) if earned_month else None})
    earned_total, spent_total = round(sum(earned), 2), round(sum(spent), 2)
    net_total = round(earned_total - spent_total, 2)
    table = Table('cash_flow', _('Паричен поток по месеци'), [
        ('month', _('Месец'), TEXT), ('income', _('Приходи'), MONEY), ('spending', _('Разходи'), MONEY),
        ('net', _('Нетно'), MONEY), ('cumulative', _('С натрупване'), MONEY),
        ('savings_rate', _('Спестявания'), PERCENT),
    ], rows, total={'month': _('Общо'), 'income': earned_total, 'spending': spent_total, 'net': net_total,
                    'cumulative': None,
                    'savings_rate': round(net_total / earned_total * 100, 1) if earned_total else None})

    by_type = (income.groupby('income_type__name')['total'].sum().sort_values(ascending=False)
               if not income.empty else pd.Series(dtype=float))
    top_value = float(by_type.iloc[0]) if not by_type.empty else 0
    type_rows = [{'name': name, 'value': round(float(value), 2), 'share': share(float(value), earned_total),
                  'width': share(float(value), top_value)} for name, value in by_type.items()]
    types_table = Table('income_by_type', _('Приходи по вид'), [
        ('name', _('Вид приход'), TEXT), ('value', _('Сума'), MONEY), ('share', _('Дял'), PERCENT),
    ], type_rows)

    return {
        'income': earned_total, 'spending': spent_total, 'net': net_total,
        'savings_rate': round(net_total / earned_total * 100, 1) if earned_total else None,
        'chart': {'months': [row['month'] for row in rows], 'income': earned, 'spending': spent,
                  'net': [row['net'] for row in rows]},
        'table': table,
        'income_types': type_rows,
        'tables': {table.key: table, types_table.key: types_table},
        'has_data': bool(earned_total or spent_total),
        'warnings': rate_warnings(spending, income),
    }


# ------------------------------------------------------------------------------------------------
# 6. Budget against actual
# ------------------------------------------------------------------------------------------------
def budget(user, filters):
    spending = load_spending(user, filters, filters.start, filters.end)
    income = load_income(user, filters, filters.start, filters.end)
    result = budget_vs_actual(user, filters, spending, income)
    table = Table('budget_vs_actual', _('Бюджет спрямо реално'), [
        ('category', _('Категория'), TEXT), ('planned', _('Планирано'), MONEY), ('actual', _('Реално'), MONEY),
        ('variance', _('Разлика'), MONEY), ('percent', _('Изпълнение'), PERCENT),
    ], result['rows'] if result else [],
        total=({'category': _('Общо'), 'planned': result['planned'], 'actual': result['actual'],
                'variance': result['variance'], 'percent': result['percent']} if result else None))
    return {
        'result': result,
        'table': table,
        'tables': {table.key: table},
        'warnings': rate_warnings(spending, income),
    }
