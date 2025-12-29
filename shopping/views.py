import json
import time
from decimal import Decimal

from django.contrib import messages
from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from .forms import CreateProductForm, UtilityBillForm, RegularShoppingForm
from users.models import CustomUser
from .helpers import load_prefill_data, get_exchange_rate, save_shopping_products
from .models import Shop, ProductCategory, MainCategory, CurrencyChoice, Shopping, Product, HouseholdShoppingList, \
    ShoppingList, ShoppingProduct
from .helpers import fetch_electricity_price, fetch_cold_water, get_heating_price
# from .fetching_utility_prices import fetch_electricity_price, fetch_cold_water, get_heating_price
# from django.utils.decorators import sync_and_async_middleware


@login_required
def shopping_list(request):
    user = request.user
    household = user.household
    product_id = request.GET.get("product_id")

    if household:
        members = CustomUser.objects.filter(household=household)
        shoppings = Shopping.objects.filter(user__in=members).order_by("-date")
    else:
        shoppings = Shopping.objects.filter(user=user).order_by("-date")

    if product_id:
        shoppings = shoppings.filter(shopping_products__product_id=product_id).distinct()

    products = Product.objects.all().order_by("name")

    context = {"shoppings": shoppings,
               'products': products,
               'selected_product_id': str(product_id) if product_id else ""
               }
    return render(request, "shopping/shopping.html", context)


@login_required
def regular_shopping(request):
    user = request.user
    household = user.household
    form = RegularShoppingForm(request.POST or None)
    create_product_form = CreateProductForm()

    if household:
        shopping_lists = HouseholdShoppingList.objects.filter(household=household, executed=True).order_by(
            '-date_generated')[:5]
    else:
        shopping_lists = ShoppingList.objects.filter(user=user, executed=True).order_by('-date_generated')[:5]

    prefill_data = load_prefill_data(request, user, household)

    if request.method == "POST" and form.is_valid():
        shopping = form.save(commit=False)
        shopping.user = user
        shopping.save()

        base_currency = shopping.currency
        date = shopping.date

        target_currencies = [c for c in CurrencyChoice.values]

        for target_currency in target_currencies:
            if base_currency == target_currency:
                continue
            try:
                get_exchange_rate(base_currency, target_currency, date)
                time.sleep(1)
            except Exception as e:
                messages.warning(request, f"Unable to fetch exchange rate for {base_currency} → {target_currency}")

        selected_products = json.loads(request.POST["selected_products"])
        save_shopping_products(selected_products, shopping, user, household)
        return redirect("shopping")

    context = {
        'form': form,
        'create_product_form': create_product_form,
        'shops': Shop.objects.all(),
        'categories': ProductCategory.objects.all().order_by('name'),
        'main_categories': MainCategory.objects.all(),
        'products': Product.objects.all().order_by('name'),
        'shopping_lists': shopping_lists,
        'prefill_json': json.dumps(prefill_data, cls=DjangoJSONEncoder),
    }
    return render(request, "shopping/regular_shopping.html", context)


@login_required
def utility_bills(request):
    selected_categories = ['Битови сметки', 'Наем', 'Финансиране', 'Инвестиции', 'Джобни']
    category = ProductCategory.objects.filter(name__in=selected_categories)
    bills = Product.objects.filter(category__in=category).order_by('name')
    electricity_price = fetch_electricity_price()
    cold_water = fetch_cold_water()
    heating_price = get_heating_price()

    if request.method == "POST":
        form = UtilityBillForm(request.POST)
        if form.is_valid():
            shopping = form.save(commit=False)
            shopping.user = request.user
            shopping.save()

            base_currency = shopping.currency
            date = shopping.date

            target_currencies = [c for c in CurrencyChoice.values]
            for target_currency in target_currencies:
                try:
                    get_exchange_rate(base_currency, target_currency, date)
                except Exception as e:
                    messages.warning(request, f"Unable to fetch exchange rate for {base_currency} → {target_currency}")

            selected_products = json.loads(request.POST.get("selected_products"))
            for product_data in selected_products:
                product = Product.objects.get(id=product_data["product_id"])
                quantity = Decimal(product_data["quantity"])
                price = Decimal(product_data["price"])
                amount = quantity * price
                not_for_household = product_data.get("not_for_household", False)

                ShoppingProduct.objects.create(
                    shopping=shopping, product=product, quantity=quantity, price=price,
                    discount=0, amount=amount, not_for_household=not_for_household
                )
            return redirect("shopping")
    else:
        form = UtilityBillForm()

    context = {
        "bills": bills,
        'form': form,
        'electricity_price': electricity_price,
        'cold_water': cold_water,
        'heating_price': heating_price,
    }
    return render(request, "shopping/utility_bills.html", context)


@login_required
def edit_shopping(request, shopping_id):
    household = request.user.household
    members = CustomUser.objects.filter(household=household)
    shopping = get_object_or_404(Shopping, id=shopping_id, user__in=members)
    shops = Shop.objects.all()
    currencies = CurrencyChoice.values

    product_id = request.GET.get("product_id")

    if request.method == "POST":
        if "delete_product" in request.POST:
            product_id = request.POST.get("delete_product")
            shopping.shopping_products.filter(id=product_id).delete()
        else:
            shopping.date = request.POST.get("date")
            shopping.shop_id = request.POST.get("shop_id")
            shopping.currency = request.POST.get("currency")
            shopping.save()

            for item in shopping.shopping_products.all():
                item.quantity = Decimal(request.POST.get(f"quantity_{item.id}", item.quantity))
                item.price = Decimal(request.POST.get(f"price_{item.id}", item.price))
                item.discount = Decimal(request.POST.get(f"discount_{item.id}", item.discount))
                item.not_for_household = f"not_for_household_{item.id}" in request.POST
                item.save()

        redirect_url = reverse("shopping")
        if product_id:
            redirect_url += f"?product_id={product_id}"
        return HttpResponseRedirect(redirect_url)

    context = {"shopping": shopping, 'shops': shops, 'product_id': product_id, 'currencies': currencies}

    return render(request, "shopping/edit_shopping.html", context)


def add_product(request):
    if request.method == "POST":
        form = CreateProductForm(request.POST)
        if form.is_valid():
            try:
                new_product = form.save()
                return JsonResponse({"id": new_product.id, "name": new_product.name})
            except IntegrityError:
                return JsonResponse({'error': "Продукт с това име вече е наличен! Въведи името в търсачката!"},
                                    status=400)
        else:
            error_msg = next(iter(form.errors.values()))[0]
            return JsonResponse({'error': error_msg}, status=400)

# Async version for utility bill. To be updated. Impossible for now due to context processors
# @sync_and_async_middleware
# @login_required
# async def utility_bills(request):
#     selected_categories = ['Битови сметки', 'Наем']
#     category_qs = ProductCategory.objects.filter(name__in=selected_categories)
#     categories = []
#     async for category in category_qs:
#         categories.append(category)
#
#     bills_qs = Product.objects.filter(category__in=categories)
#     bills = []
#     async for bill in bills_qs:
#         bills.append(bill)
#
#     electricity_price = await fetch_electricity_price()
#     cold_water = await fetch_cold_water()
#     heating_price = await get_heating_price()
#
#     if request.method == "POST":
#         form = UtilityBillForm(request.POST)
#         if form.is_valid():
#             shopping = form.save(commit=False)
#             shopping.user = request.user
#             await shopping.asave()
#
#             base_currency = shopping.currency
#             date = shopping.date
#
#             target_currencies = [c for c in CurrencyChoice.values]
#             for target_currency in target_currencies:
#                 try:
#                     await get_exchange_rate(base_currency, target_currency, date)
#                 except Exception:
#                     messages.warning(request, f"Unable to fetch exchange rate for {base_currency} → {target_currency}")
#
#             selected_products = json.loads(request.POST.get("selected_products"))
#             for product_data in selected_products:
#                 product = await Product.objects.aget(id=product_data["product_id"])
#                 quantity = Decimal(product_data["quantity"])
#                 price = Decimal(product_data["price"])
#                 amount = quantity * price
#                 not_for_household = product_data.get("not_for_household", False)
#
#                 await ShoppingProduct.objects.acreate(
#                     shopping=shopping, product=product, quantity=quantity, price=price,
#                     discount=0, amount=amount, not_for_household=not_for_household
#                 )
#             return redirect("shopping")
#     else:
#         form = UtilityBillForm()
#
#     context = {
#         "bills": bills,
#         'form': form,
#         'electricity_price': electricity_price,
#         'cold_water': cold_water,
#         'heating_price': heating_price,
#     }
#     return render(request, "shopping/utility_bills.html", context)