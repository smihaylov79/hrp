from calendar import month_name
from collections import defaultdict
from decimal import Decimal

import pandas as pd
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Count, Max, Min, Avg, Q
from django.db.models.functions import TruncMonth, TruncWeek, ExtractWeek
from django.shortcuts import render, get_object_or_404
from inventory.models import *
from shopping.models import *
import json
from django.views.generic import FormView, TemplateView
from .forms import *
from datetime import date, datetime
from .utils import *



# Create your views here.


class ReportsHomeView(LoginRequiredMixin, TemplateView):
    template_name = 'reports/reports_home.html'


class SpendingsView(FormView):
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

            df = db_to_df(shopping_data, currency)
            if data_for_monthly_comparison:
                data_for_monthly_comparison = data_for_monthly_comparison.select_related('shopping', 'product__category__main_category')
                df_monthly_comparison = db_to_df(data_for_monthly_comparison, currency)
            else:
                df_monthly_comparison = df


            context = self.get_context_data(form=form, )
            context.update({'monthly_data': json.dumps(monthly_weekly_spending(df)[0]),
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


class SpendingsByShopView(FormView):
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
                shopping_data = shopping_data.filter(date__range=(date_from, date_to))

            shopping_data = shopping_data.select_related('shopping', 'shop', 'product__category__main_category')

            df = db_to_df(shopping_data, currency)

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
                    # Find the lowest numeric price (ignoring dashes)
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
                            }

            )

        return self.render_to_response(context)



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
    price_data = []

    if selected_product_id:
        product = get_object_or_404(Product, id=selected_product_id)

        if household:
            price_changes = ShoppingProduct.objects.filter(shopping__user__in=members, product=product) \
                .values("shopping__date").annotate(avg_price=Avg("price")).order_by("shopping__date")
        else:
            price_changes = ShoppingProduct.objects.filter(shopping__user=user, product=product) \
                .values("shopping__date").annotate(avg_price=Avg("price")).order_by("shopping__date")

        price_data = [{"date": entry["shopping__date"].strftime("%Y-%m-%d"), "price": float(entry["avg_price"])} for
                      entry in price_changes]

    context = {
        "products": products,
        "selected_product_id": selected_product_id,
        "price_data": json.dumps(price_data) if price_data else "[]"
    }

    return render(request, "reports/price_history.html", context)


def spendings_by_shop(request):
    user = request.user
    household = user.household

    selected_shop_ids = request.GET.getlist("shops")
    main_categories = MainCategory.objects.all()

    main_category_name = ""

    main_category_filter = request.GET.get("main_category", "")
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    if household:
        members = CustomUser.objects.filter(household=household)
        user_shops = Shop.objects.filter(id__in=Shopping.objects.filter(user__in=members).values("shop")).distinct()
        shopping_data = ShoppingProduct.objects.filter(shopping__user__in=members)
    else:
        user_shops = Shop.objects.filter(id__in=Shopping.objects.filter(user=user).values("shop")).distinct()
        shopping_data = ShoppingProduct.objects.filter(shopping__user=user)

    if main_category_filter and main_category_filter.strip():
        shopping_data = shopping_data.filter(product__category_id__main_category_id=main_category_filter)
        main_category = main_categories.filter(id=main_category_filter).first()
        main_category_name = main_category.name

    if start_date and end_date:
        shopping_data = shopping_data.filter(shopping__date__range=[start_date, end_date])

    # Global average price per product
    avg_price_changes = shopping_data.values("product__name").annotate(
        avg_price=Avg("price")
    )
    for item in avg_price_changes:
        item["avg_price"] = round(item["avg_price"], 2)

    shop_spending_totals = shopping_data.values("shopping__shop__name").annotate(
        total_spent=Sum("amount")
    )
    spending_chart_data = [
        {
            "name": entry["shopping__shop__name"],
            "y": float(entry["total_spent"])
        }
        for entry in shop_spending_totals
    ]

    # If shops are selected, build comparison data
    shop_price_changes = []
    if selected_shop_ids:
        selected_shops = user_shops.filter(id__in=selected_shop_ids)

        for shop in selected_shops:
            shop_avg_prices = shopping_data.filter(shopping__shop=shop).values("product__name").annotate(
                shop_avg_price=Avg("price")
            )

            shop_data = {
                "shop_name": shop.name,
                "shop_id": shop.id,
                "prices": {
                    item["product__name"]: round(item["shop_avg_price"], 2)
                    for item in shop_avg_prices
                }
            }

            shop_price_changes.append(shop_data)

    context = {
        "user_shops": user_shops,
        "selected_shops": selected_shop_ids,
        "avg_price_changes": avg_price_changes,
        "shop_price_changes": shop_price_changes,
        "main_categories": main_categories,
        "main_category_filter": main_category_filter,
        "main_category_name": main_category_name,
        "spending_chart_data": json.dumps(spending_chart_data),
    }

    return render(request, "reports/spendings_by_shop.html", context)
