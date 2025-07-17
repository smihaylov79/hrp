from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Count, Max, Min, Avg
from django.db.models.functions import TruncMonth, TruncWeek, ExtractWeek
from django.shortcuts import render, get_object_or_404
from inventory.models import *
from shopping.models import *
import json
from django.views.generic import FormView, TemplateView
from .forms import *
from datetime import date
from .utils import calculate_price_changes


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
            household_filter = form.cleaned_data.get("not_for_household_filter", "all")

            if household_filter == "household":
                shopping_data = shopping_data.filter(not_for_household=False)
            elif household_filter == "external":
                shopping_data = shopping_data.filter(not_for_household=True)

            if main_category:
                shopping_data = shopping_data.filter(product__category_id__main_category_id=main_category.id)

            if date_from and date_to:
                shopping_data = shopping_data.filter(shopping__date__range=(date_from, date_to))
            elif date_from:
                shopping_data = shopping_data.filter(shopping__date__gte=date_from)
            elif date_to:
                shopping_data = shopping_data.filter(shopping__date__lte=date_to)

            total_spent = shopping_data.aggregate(total=Sum('amount'))['total']
            monthly_spent = shopping_data.annotate(month=TruncMonth('shopping__date')).values('month').annotate(
                total_amount=Sum('amount')).order_by('month')
            weekly_spent = shopping_data.annotate(week=ExtractWeek('shopping__date')).values('week').annotate(
                total_amount=Sum('amount')).order_by('week')

            monthly_data = [
                {'month': entry['month'].strftime('%m.%Y'), 'total': float(entry['total_amount'])} for entry in
                monthly_spent
            ]
            weekly_data = [{'week': entry['week'], 'total': float(entry['total_amount'])} for entry in weekly_spent]


            main_category_spending = shopping_data.values("product__category__main_category__name").annotate(
                total_spent=Sum("amount"))
            subcategory_spending = shopping_data.values("product__category__name").annotate(total_spent=Sum("amount"))

            main_chart_data = [
                {"name": entry["product__category__main_category__name"], "y": float(entry["total_spent"])}
                for entry in main_category_spending]
            sub_chart_data = [{"name": entry["product__category__name"], "y": float(entry["total_spent"])}
                              for entry in subcategory_spending]

            shoppings_count = shopping_data.aggregate(shoppings_count=Count('shopping', distinct=True))['shoppings_count']
            most_purchased = (
                shopping_data.values('product__name').annotate(purchase_count=Count('id')).order_by('-purchase_count')[:5]
            )
            most_purchased_names = ', '.join([entry['product__name'] for entry in most_purchased])
            biggest_spent = shopping_data.values('product__name').annotate(spent=Max('amount')).order_by('-spent').first()
            lowest_price = shopping_data.exclude(price=0).values('product__name').annotate(price=Min('price')).order_by('price').first()
            highest_price = shopping_data.values('product__name').annotate(price=Max('price')).order_by('-price').first()

            price_changes = calculate_price_changes(shopping_data.exclude(price=0).values(
                                            'product__name','price', 'shopping__date').order_by('product__name', 'shopping__date'))
            top_increase = price_changes[0][:1][0] if price_changes[0] else None
            top_decrease = price_changes[1][:1][0] if price_changes[1] else None


            context = self.get_context_data(form=form, )
            context.update({'monthly_data': json.dumps(monthly_data),
                            'weekly_data': json.dumps(weekly_data),
                            'total_spent': total_spent,
                            'main_category_name': main_category.name if main_category else '',
                            'main_chart_data': json.dumps(main_chart_data),
                            'sub_chart_data': json.dumps(sub_chart_data),
                            'most_purchased': most_purchased,
                            'shoppings_count': shoppings_count,
                            'most_purchased_names': most_purchased_names,
                            'biggest_spent': biggest_spent,
                            'lowest_price': lowest_price,
                            'highest_price': highest_price,
                            'top_increase': top_increase,
                            'top_decrease': top_decrease,
                            })
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

        price_data = [{"date": entry["shopping__date"].strftime("%Y-%m-%d"), "price": float(entry["avg_price"])} for entry in price_changes]

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

    # TODO refine the filters to work together

    return render(request, "reports/spendings_by_shop.html", context)

