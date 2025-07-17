from decimal import Decimal
import json
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError
from django.db.models import Sum, Count, Case, When, IntegerField
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.views.decorators.http import require_POST

from forum.models import Category
from .models import *
from inventory.models import *
from .forms import *
from users.models import *


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


    # paginator = Paginator(shoppings, 15)
    # page_number = request.GET.get("page")
    # page_obj = paginator.get_page(page_number)

    products = Product.objects.all()

    context = {"shoppings": shoppings,
               'products': products,
               'selected_product_id': str(product_id) if product_id else ""
               }
    return render(request, "shopping/shopping.html", context)


@login_required
def edit_shopping(request, shopping_id):
    household = request.user.household
    members = CustomUser.objects.filter(household=household)
    shopping = get_object_or_404(Shopping, id=shopping_id, user__in=members)
    shops = Shop.objects.all()

    product_id = request.GET.get("product_id")

    if request.method == "POST":
        if "delete_product" in request.POST:
            product_id = request.POST.get("delete_product")
            shopping.shopping_products.filter(id=product_id).delete()
        else:
            shopping.date = request.POST.get("date")
            shopping.shop_id = request.POST.get("shop_id")
            shopping.save()

            for item in shopping.shopping_products.all():
                item.quantity = Decimal(request.POST.get(f"quantity_{item.id}", item.quantity))
                item.price = Decimal(request.POST.get(f"price_{item.id}", item.price))
                item.discount = Decimal(request.POST.get(f"discount_{item.id}", item.discount))
                item.not_for_household = f"not_for_household_{item.id}" in request.POST
                item.save()
            # return redirect("shopping")

        redirect_url = reverse("shopping")
        if product_id:
            redirect_url += f"?product_id={product_id}"
        return HttpResponseRedirect(redirect_url)

        # return redirect("edit_shopping", shopping_id=shopping.id)


    context = {"shopping": shopping, 'shops': shops, 'product_id': product_id}

    return render(request, "shopping/edit_shopping.html", context)


@login_required
def make_shopping(request):
    user = request.user
    household = user.household

    shops = Shop.objects.all()
    categories = ProductCategory.objects.all().order_by('name')
    main_categories = MainCategory.objects.all()
    all_products = Product.objects.all().order_by('name')

    if household:
        shopping_lists = HouseholdShoppingList.objects.filter(household=household, executed=True).order_by('-date_generated')[:5]
    else:
        shopping_lists = ShoppingList.objects.filter(user=user, executed=True).order_by('-date_generated')[:5]

    selected_category_id = request.GET.get("category")

    # load from shopping list
    selected_list_id = request.GET.get("list")
    prefill_data = []

    if selected_list_id:
        try:
            if household:
                shopping_list = HouseholdShoppingList.objects.get(id=selected_list_id, household=household)
            else:
                shopping_list = ShoppingList.objects.get(id=selected_list_id, user=user)
            for item_name in shopping_list.items:
                product = Product.objects.filter(name=item_name).first()
                if product:
                    last_price = 0.00
                    shoppings = Shopping.objects.filter(user=user)
                    shoppings_ids = [sh.id for sh in shoppings]
                    shopping_product = ShoppingProduct.objects.filter(product=product.id, shopping__in=shoppings_ids).order_by('id').last()
                    if shopping_product:
                        last_price = shopping_product.price
                    prefill_data.append({
                    "product_id": product.id,
                    "name": product.name,
                    "quantity": 1,
                    "price": last_price,
                    "discount": 0,
                    "not_for_household": False,
                })
        except ShoppingList.DoesNotExist:
            pass

    if selected_category_id:
        all_products = all_products.filter(category_id=selected_category_id)



    context = {
        "shops": shops,
        "categories": categories,
        "products": all_products,
        "main_categories": main_categories,
        "selected_category": selected_category_id,
        "shopping_lists": shopping_lists,
        "prefill_json": json.dumps(prefill_data, cls=DjangoJSONEncoder),

    }

    return render(request, "shopping/make_shopping.html", context)


@login_required
def save_shopping(request):
    if request.method == "POST":

        user = request.user
        household = user.household

        shop_id = request.POST["shop_id"]
        date = request.POST["date"]
        selected_products = json.loads(request.POST["selected_products"])

        shop = Shop.objects.get(id=shop_id)
        shopping = Shopping.objects.create(user=user, date=date, shop=shop)

        for product_data in selected_products:
            product = Product.objects.get(id=product_data["product_id"])
            quantity = Decimal(product_data["quantity"])
            price = Decimal(product_data["price"])
            discount = Decimal(product_data["discount"] if product_data["discount"] else 0)
            amount = quantity * price - discount

            not_for_household = product_data['not_for_household']

            ShoppingProduct.objects.create(
                shopping=shopping, product=product, quantity=quantity, price=price,
                discount=discount, amount=amount, not_for_household=not_for_household
            )
            if household:
                inventory_product, created = HouseholdInventoryProduct.objects.get_or_create(
                    household=household, product=product, category=product.category,
                    defaults={"quantity": 0, "amount": 0, "inventory_related": True}
                )
                if inventory_product.inventory_related and not not_for_household:
                    inventory_product.quantity += quantity
                    inventory_product.amount += amount
                    inventory_product.calculate_average_price()
                    inventory_product.save()

                household_product_category, created = HouseholdProductCategory.objects.get_or_create(household=household,
                                                                                           product_category=product.category)
                household_product_category.save()

            else:
                inventory_product, created = InventoryProduct.objects.get_or_create(
                    user=request.user, product=product, category=product.category,
                    defaults={"quantity": 0, "amount": 0, "inventory_related": True}
                    )
                if inventory_product.inventory_related and not not_for_household:
                    inventory_product.quantity += quantity
                    inventory_product.amount += amount
                    inventory_product.calculate_average_price()
                    inventory_product.save()

                user_product_category, created = UserProductCategory.objects.get_or_create(user=request.user, product_category=product.category)
                user_product_category.save()

        return redirect("make_shopping")

    return redirect("make_shopping")


def add_product(request):
    if request.method == "POST":
        category_id = request.POST.get("category_id")
        product_name = request.POST.get("new_product_name")
        calories = request.POST.get("new_calories")

        if not category_id or not product_name or not calories:
            return JsonResponse({"error": "Всички полета са задължителни!"}, status=400)

        category = ProductCategory.objects.get(id=category_id)
        try:
            new_product = Product.objects.create(name=product_name, calories=calories, category=category)
        except IntegrityError:
            return JsonResponse({'error': "Продукт с това име вече е наличен! Въведи името в търсачката!"}, status=400)

        return JsonResponse({"id": new_product.id, "name": new_product.name})


@login_required
def utility_bills(request):
    selected_categories = ['Битови сметки', 'Наем']
    category = ProductCategory.objects.filter(name__in=selected_categories)
    bills = Product.objects.filter(category__in=category)

    if request.method == "POST":
        form = UtilityBillForm(request.POST)
        if form.is_valid():
            shopping = form.save(commit=False)
            shopping.user = request.user
            shopping.save()

            selected_products = json.loads(request.POST.get("selected_products"))
            for product_data in selected_products:
                product = Product.objects.get(id=product_data["product_id"])
                quantity = Decimal(product_data["quantity"])
                price = Decimal(product_data["price"])
                amount = quantity * price

                ShoppingProduct.objects.create(
                    shopping=shopping, product=product, quantity=quantity, price=price,
                    discount=0, amount=amount
                )
            return redirect("shopping")
    else:
        form = UtilityBillForm()

    context = {
        "bills": bills,
        'form': form,
    }
    return render(request, "shopping/utility_bills.html", context)
