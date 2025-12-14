from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.shortcuts import render, redirect
import json
from django.views.generic import FormView, TemplateView

from income.models import Income
from .forms import *
from .utils import *


# Create your views here.


class ReportsHomeView(LoginRequiredMixin, TemplateView):
    template_name = 'reports/reports_home.html'


class SpendingsView(LoginRequiredMixin, FormView):
    template_name = 'reports/spendings_history.html'
    form_class = SpendingsReportFilterForm

    def get(self, request, *args, **kwargs):
        form = self.form_class(self.request.GET or None)
        context = self.get_context_data(form=form)

        if form.is_valid():
            user = self.request.user
            household = user.household

            if household:
                members = CustomUser.objects.filter(household=household)
                shopping_data = ShoppingProduct.objects.filter(shopping__user__in=members)

            else:
                shopping_data = ShoppingProduct.objects.filter(shopping__user=user)

            main_category = form.cleaned_data.get('main_category')
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')
            currency = form.cleaned_data.get('currency')
            household_filter = form.cleaned_data.get("not_for_household_filter", "all")

            if household_filter == "household":
                shopping_data = shopping_data.filter(not_for_household=False)
            elif household_filter == "external":
                shopping_data = shopping_data.filter(not_for_household=True)

            if main_category:
                shopping_data = shopping_data.filter(product__category_id__main_category_id=main_category.id)

            data_for_monthly_comparison = None

            if date_from and date_to:
                current_period = Q(shopping__date__range=(date_from, date_to))
                previous_years_period = Q()
                for offset in [1, 2]:
                    prev_from = date_from.replace(year=date_from.year - offset)
                    prev_to = date_to.replace(year=date_to.year - offset)
                    previous_years_period |= Q(shopping__date__range=(prev_from, prev_to))
                data_for_monthly_comparison = shopping_data.filter(current_period | previous_years_period)

                shopping_data = shopping_data.filter(current_period)

            shopping_data = shopping_data.select_related('shopping', 'product__category__main_category')

            shoppings_count = shopping_data.aggregate(shoppings_count=Count('shopping', distinct=True))[
                'shoppings_count']
            most_purchased = (
                shopping_data.values('product__name').annotate(purchase_count=Count('id')).order_by('-purchase_count')[
                :5]
            )
            most_purchased_names = ', '.join([entry['product__name'] for entry in most_purchased])

            df = None

            if shopping_data:
                df = db_to_df(shopping_data, currency)

            if data_for_monthly_comparison:
                data_for_monthly_comparison = data_for_monthly_comparison.select_related('shopping',
                                                                                         'product__category__main_category')
                df_monthly_comparison = db_to_df(data_for_monthly_comparison, currency)
            else:
                df_monthly_comparison = df

# Newly added 10.11
            main_category_monthly = (
                df.groupby(['month', 'product__category__main_category__name'])['total']
                .sum()
                .reset_index()
            )

            # Prepare Highcharts series
            month_labels = sorted(main_category_monthly['month'].unique())
            main_categories = main_category_monthly['product__category__main_category__name'].unique()

            main_category_series = []
            for category in main_categories:
                data = []
                for month in month_labels:
                    value = main_category_monthly[
                        (main_category_monthly['month'] == month) &
                        (main_category_monthly['product__category__main_category__name'] == category)
                        ]['total']
                    data.append(round(value.values[0], 2) if not value.empty else 0)
                main_category_series.append({'name': category, 'data': data})

            # print(main_category_monthly)
            #
            # context.update({
            #     'main_category_series': json.dumps(main_category_series),
            #     'main_category_month_labels': json.dumps(month_labels),
            # })
            # context.update({
            #     'main_category_monthly_data': json.dumps(main_category_monthly.to_dict(orient='records')),
            # })
            # end of added 10.11

            context = self.get_context_data(form=form, )
            if df is not None and not df.empty:
                context.update({'main_category_monthly_data': json.dumps(main_category_monthly.to_dict(orient='records')),
                                'monthly_data': json.dumps(monthly_weekly_spending(df)[0]),
                                'weekly_data': json.dumps(monthly_weekly_spending(df)[1]),
                                'total_spent': round(df['total'].sum(), 2),
                                'main_category_name': main_category.name if main_category else '',
                                'main_chart_data': json.dumps(by_category_spending(df)[0]),
                                'sub_chart_data': json.dumps(by_category_spending(df)[1]),
                                'shoppings_count': shoppings_count,
                                'most_purchased_names': most_purchased_names,
                                'biggest_spent': by_product_statistics(df)[0],
                                'lowest_price': by_product_statistics(df)[1],
                                'highest_price': by_product_statistics(df)[2],
                                'top_increase': calculate_price_changes(df)[0],
                                'top_decrease': calculate_price_changes(df)[1],
                                'yearly_series': json.dumps(monthly_compare_chart(df_monthly_comparison)[0]),
                                'month_labels': json.dumps(monthly_compare_chart(df_monthly_comparison)[1]),
                                })
        return self.render_to_response(context)


class SpendingsByShopView(LoginRequiredMixin, FormView):
    template_name = 'reports/by_shop.html'
    form_class = SpendingsReportFilterForm

    def get(self, request, *args, **kwargs):
        user = self.request.user
        household = user.household
        if household:
            members = CustomUser.objects.filter(household=household)
            user_shops = Shop.objects.filter(
                id__in=Shopping.objects.filter(user__in=members).values("shop")).distinct()
            shopping_data = ShoppingProduct.objects.filter(shopping__user__in=members)
        else:
            user_shops = Shop.objects.filter(id__in=Shopping.objects.filter(user=user).values("shop")).distinct()
            shopping_data = ShoppingProduct.objects.filter(shopping__user=user)

        form = self.form_class(self.request.GET or None, user_shops=user_shops)
        context = self.get_context_data(form=form)

        if form.is_valid():
            main_category = form.cleaned_data.get('main_category')
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')
            currency = form.cleaned_data.get('currency')
            household_filter = form.cleaned_data.get("not_for_household_filter", "all")
            selected_shop_ids = form.cleaned_data.get("shops")

            selected_shops = user_shops.filter(id__in=selected_shop_ids)

            if selected_shops:
                shopping_data = shopping_data.filter(shopping__shop__id__in=selected_shops)

            if household_filter == "household":
                shopping_data = shopping_data.filter(not_for_household=False)
            elif household_filter == "external":
                shopping_data = shopping_data.filter(not_for_household=True)

            if main_category:
                shopping_data = shopping_data.filter(product__category_id__main_category_id=main_category.id)

            if date_from and date_to:
                shopping_data = shopping_data.filter(shopping__date__range=(date_from, date_to))

            shopping_data = shopping_data.select_related('shopping', 'product__category__main_category')


            df = None
            shop_price_changes = None
            avg_price_changes = None
            spending_chart_data = None
            total_for_selection = 0

            if shopping_data:
                df = db_to_df(shopping_data, currency)

                total_for_selection = df['total'].sum()

                avg_price_changes = df.groupby('product__name')['total'].mean()

                shop_spending_totals = df.groupby('shopping__shop__name')['total'].sum()

                spending_chart_data = [{
                "name": shop,
                "y": total
            } for shop, total in shop_spending_totals.items()]

                shop_price_changes = df.groupby(['product__name', 'shopping__shop__name'])['converted_price'].mean().round(
                2).unstack().fillna('-')
                shop_price_changes['Обща средна цена'] = df.groupby('product__name')['converted_price'].mean().round(2)

            highlighted_table = []

            if selected_shops:
                for product, row in shop_price_changes.iterrows():
                    prices_only = row.drop('Обща средна цена')
                    numeric_prices = [price for price in prices_only if isinstance(price, (int, float))]
                    min_price = min(numeric_prices) if numeric_prices else None

                    row_data = {
                        'product': product,
                        'overall_avg': row['Обща средна цена'],
                        'shops': []
                    }

                    for shop in prices_only.index:
                        value = row[shop]
                        row_data['shops'].append({
                            'shop': shop,
                            'price': value if isinstance(value, (int, float)) else None,
                            'is_lowest': value == min_price
                        })
                    highlighted_table.append(row_data)

            context.update({"spending_chart_data": json.dumps(spending_chart_data),
                            "avg_price_changes": avg_price_changes,
                            "shop_price_changes": shop_price_changes,
                            'user_shops': user_shops,
                            'highlighted_table': highlighted_table if selected_shops else None,
                            "selected_shop_ids": [str(shop.id) for shop in selected_shop_ids],
                            'total_for_selection': total_for_selection,
                            }

                           )

        return self.render_to_response(context)


def price_changes(request):
    user = request.user
    household = user.household

    total_inflation_data = {}
    if household:
        members = [m for m in CustomUser.objects.filter(household=household)]
        inflation_baskets = HouseholdInflationBasket.objects.all()
        for basket in inflation_baskets:
            selected_ids = HouseholdInflationBasketItem.objects.filter(basket=basket).values_list("product_id",
                                                                                                  flat=True)
            shopping_products = ShoppingProduct.objects.filter(shopping__user__in=members,
                                                               product__household_inventory_product__in=selected_ids)
            shopping_products = shopping_products.select_related('shopping', 'shop', 'product__category__main_category')
            shopping_products = db_to_df(shopping_products, 'BGN')
            inflation_data = calculate_inflation(monthly_weekly_spending(shopping_products)[0])
            total_change = ((inflation_data['total'].iloc[-1] - inflation_data['total'].iloc[0]) /
                            inflation_data['total'].iloc[0]) * 100
            total_change = round(total_change, 2)
            basket.total_change = total_change
            total_inflation_data[basket.id] = inflation_data, total_change

    else:
        inflation_baskets = UserInflationBasket.objects.all()
        for basket in inflation_baskets:
            selected_ids = UserInflationBasketItem.objects.filter(basket=basket).values_list("product_id", flat=True)
            shopping_products = ShoppingProduct.objects.filter(shopping__user=user,
                                                               product__inventory_product__in=selected_ids)
            shopping_products = shopping_products.select_related('shopping', 'shop', 'product__category__main_category')
            shopping_products = db_to_df(shopping_products, 'BGN')
            inflation_data = calculate_inflation(monthly_weekly_spending(shopping_products)[0])
            total_change = ((inflation_data['total'].iloc[-1] - inflation_data['total'].iloc[0]) /
                            inflation_data['total'].iloc[0]) * 100
            total_change = round(total_change, 2)
            basket.total_change = total_change
            total_inflation_data[basket.id] = inflation_data, total_change

    chart_data = {}
    for basket_id, (inflation_data, total_change) in total_inflation_data.items():
        chart_data[basket_id] = {
            'months': inflation_data['month'].tolist(),
            'inflation_values': inflation_data['inflation_mom'].fillna(0).round(2).tolist(),
            'total_inflation': round(total_change, 2),
        }

    products, selected_product_id, price_data, currency = product_price_history(request)

    currencies = CurrencyChoice.choices

    context = {
        'inflation_baskets': inflation_baskets,
        'chart_data_json': json.dumps(chart_data),
        "products": products,
        "selected_product_id": selected_product_id,
        "price_data": json.dumps(price_data),
        'currency': currency,
        'currencies': currencies,

    }
    return render(request, 'reports/price_changes.html', context)


@login_required
def create_inflation_basket(request):
    user = request.user
    household = user.household
    if household:
        products = HouseholdInventoryProduct.objects.all().order_by('product__name')
    else:
        products = InventoryProduct.objects.all().order_by('product__name')
    context = {
        'products': products,
    }
    return render(request, 'reports/create_inflation_basket.html', context)


def save_inflation_basket(request):
    user = request.user
    household = user.household
    if request.method == "POST":
        name = request.POST['name']
        product_ids = request.POST.getlist("product_id[]")
        if household:
            basket = HouseholdInflationBasket.objects.create(household=household, name=name)
            for i in range(len(product_ids)):
                product = HouseholdInventoryProduct.objects.get(id=product_ids[i])
                HouseholdInflationBasketItem.objects.create(basket=basket, product=product)

        else:
            basket = UserInflationBasket.objects.create(user=user, name=name)
            for i in range(len(product_ids)):
                product = InventoryProduct.objects.get(id=product_ids[i])
                UserInflationBasketItem.objects.create(basket=basket, product=product)
        return redirect('price_changes')


@login_required
def edit_inflation_basket(request, basket_id):
    user = request.user
    household = user.household
    if household:
        basket = HouseholdInflationBasket.objects.get(id=basket_id, household=user.household)
        products = HouseholdInventoryProduct.objects.all().order_by('product__name')
        selected_ids = HouseholdInflationBasketItem.objects.filter(basket=basket).values_list("product_id", flat=True)

    else:
        basket = UserInflationBasket.objects.get(id=basket_id, user=user)
        products = InventoryProduct.objects.all().order_by('product__name')
        selected_ids = UserInflationBasketItem.objects.filter(basket=basket).values_list("product_id", flat=True)

    if request.method == "POST":
        basket.name = request.POST['name']
        basket.save()
        new_ids = request.POST.getlist("product_id[]")
        if household:
            basket.household_basket_items.all().delete()
            for i in new_ids:
                product = HouseholdInventoryProduct.objects.get(id=i)
                HouseholdInflationBasketItem.objects.create(basket=basket, product=product)
        else:
            basket.user_basket_items.all().delete()
            for i in new_ids:
                product = InventoryProduct.objects.get(id=i)
                UserInflationBasketItem.objects.create(basket=basket, product=product)
        return redirect('price_changes')

    context = {
        'basket': basket,
        'products': products,
        'selected_ids': selected_ids,
    }
    return render(request, 'reports/edit_inflation_basket.html', context)


@login_required
def income_analysis(request):
    user = request.user

    # ако има household → взимаме всички приходи на household-а
    if user.household:
        incomes_qs = Income.objects.filter(user__household=user.household)
    else:
        incomes_qs = Income.objects.filter(user=user)

    # превръщаме в DataFrame
    data = list(incomes_qs.values("income_type__name", "amount", "currency", "date_received"))
    df = pd.DataFrame(data)

    analysis = {}
    if not df.empty:
        # групиране по тип приход
        by_type = df.groupby("income_type__name")["amount"].sum().sort_values(ascending=False)
        analysis["by_type"] = by_type.to_dict()

        # групиране по месец
        df["month"] = pd.to_datetime(df["date_received"]).dt.to_period("M")
        by_month = df.groupby("month")["amount"].sum()
        analysis["by_month"] = by_month.to_dict()

        # обща сума
        analysis["total_income"] = df["amount"].sum()

    return render(request, "reports/income_analysis.html", {"analysis": analysis})


class IncomeView(LoginRequiredMixin, FormView):
    template_name = 'reports/income_analysis.html'
    form_class = IncomeReportFilterForm  # подобна на SpendingsReportFilterForm, но за приходи

    def get(self, request, *args, **kwargs):
        form = self.form_class(self.request.GET or None)
        context = self.get_context_data(form=form)

        if form.is_valid():
            user = self.request.user
            household = user.household

            if household:
                members = CustomUser.objects.filter(household=household)
                income_data = Income.objects.filter(user__in=members)
            else:
                income_data = Income.objects.filter(user=user)

            income_type = form.cleaned_data.get('income_type')
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')
            currency = form.cleaned_data.get('currency')

            if income_type:
                income_data = income_data.filter(income_type=income_type)

            if date_from and date_to:
                current_period = Q(date_received__range=(date_from, date_to))
                previous_years_period = Q()
                for offset in [1, 2]:
                    prev_from = date_from.replace(year=date_from.year - offset)
                    prev_to = date_to.replace(year=date_to.year - offset)
                    previous_years_period |= Q(date_received__range=(prev_from, prev_to))
                data_for_monthly_comparison = income_data.filter(current_period | previous_years_period)
                income_data = income_data.filter(current_period)
            else:
                data_for_monthly_comparison = None

            df = None
            if income_data.exists():
                df = income_db_to_df(income_data, currency)  # твоя utils функция за конверсия

            if data_for_monthly_comparison:
                df_monthly_comparison = income_db_to_df(data_for_monthly_comparison, currency)
            else:
                df_monthly_comparison = df

            if df is not None and not df.empty:
                # групиране по тип приход
                by_type = df.groupby("income_type__name")["total"].sum().reset_index()

                # групиране по месец
                df["month"] = pd.to_datetime(df["date_received"]).dt.to_period("M")
                by_month = df.groupby("month")["total"].sum().reset_index()

                # Highcharts series
                month_labels = sorted(by_month["month"].astype(str).unique())
                monthly_series = [{"name": "Приходи", "data": by_month["total"].round(2).tolist()}]

                type_series = [{"name": row["income_type__name"], "y": round(row["total"], 2)} for _, row in by_type.iterrows()]
                selected_currency = form.cleaned_data.get("currency") or "BGN"
                context.update({
                    "total_income": round(df["total"].sum(), 2),
                    "monthly_series": json.dumps(monthly_series),
                    "month_labels": json.dumps(month_labels),
                    "type_series": json.dumps(type_series),
                    "selected_currency": selected_currency,
                })

        return self.render_to_response(context)


# def income_spendings_comparison(request):
#     user = request.user
#     household = user.household
#
#     if household:
#         members = CustomUser.objects.filter(household=household)
#         income_qs = Income.objects.filter(user__in=members)
#         spendings_qs = ShoppingProduct.objects.filter(shopping__user__in=members)
#     else:
#         income_qs = Income.objects.filter(user=user)
#         spendings_qs = ShoppingProduct.objects.filter(shopping__user=user)
#
#     print("Income count:", income_qs.count())
#     print("Spendings count:", spendings_qs.count())
#
#     currency = request.GET.get("currency", "BGN")
#     comparison_df = income_vs_spendings(income_qs, spendings_qs, currency)
#
#     month_labels = comparison_df["month"].astype(str).tolist()
#     income_series = comparison_df["total_income"].astype(float).round(2).tolist()
#     spendings_series = comparison_df["total_spendings"].astype(float).round(2).tolist()
#     net_series = comparison_df["net_balance"].astype(float).round(2).tolist()
#
#     context = {
#         "month_labels": json.dumps(month_labels),
#         "income_series": json.dumps([{"name": "Приходи", "data": income_series}]),
#         "spendings_series": json.dumps([{"name": "Разходи", "data": spendings_series}]),
#         "net_series": json.dumps([{"name": "Нетен баланс", "data": net_series}]),
#         "selected_currency": currency,
#     }
#     return render(request, "reports/income_spendings_comparison.html", context)


def income_spendings_comparison(request):
    form = IncomeSpendingsComparisonForm(request.GET or None)

    user = request.user
    household = user.household

    if household:
        members = CustomUser.objects.filter(household=household)
        income_qs = Income.objects.filter(user__in=members)
        spendings_qs = ShoppingProduct.objects.filter(shopping__user__in=members)
    else:
        income_qs = Income.objects.filter(user=user)
        spendings_qs = ShoppingProduct.objects.filter(shopping__user=user)

    # филтри по период
    if form.is_valid():
        date_from = form.cleaned_data.get("date_from")
        date_to = form.cleaned_data.get("date_to")
        currency = form.cleaned_data.get("currency") or "BGN"

        if date_from and date_to:
            income_qs = income_qs.filter(date_received__range=(date_from, date_to))
            spendings_qs = spendings_qs.filter(shopping__date__range=(date_from, date_to))

        comparison_df = income_vs_spendings(income_qs, spendings_qs, currency)

        month_labels = comparison_df["month"].astype(str).tolist()
        income_series = [{"name": "Приходи", "data": comparison_df["total_income"].astype(float).round(2).tolist()}]
        spendings_series = [{"name": "Разходи", "data": comparison_df["total_spendings"].astype(float).round(2).tolist()}]
        net_series = [{"name": "Нетен баланс", "data": comparison_df["net_balance"].astype(float).round(2).tolist()}]

        cumulative_series = [{
            "name": "Кумулативен баланс",
            "type": "line",
            "data": comparison_df["cumulative_net"].astype(float).round(2).tolist()
        }]

        context = {
            "form": form,
            "month_labels": json.dumps(month_labels),
            "income_series": json.dumps(income_series),
            "spendings_series": json.dumps(spendings_series),
            "net_series": json.dumps(net_series),
            "selected_currency": currency,
            "cumulative_series": json.dumps(cumulative_series),
        }

    else:
        context = {"form": form}

    return render(request, "reports/income_spendings_comparison.html", context)