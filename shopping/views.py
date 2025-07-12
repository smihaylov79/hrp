from decimal import Decimal
import json
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Sum, Count, Case, When, IntegerField
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from .models import *
from inventory.models import InventoryProduct, UserProductCategory


def shopping_list(request):
    shoppings = Shopping.objects.filter(user=request.user).order_by("-date")

    paginator = Paginator(shoppings, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {"page_obj": page_obj}
    return render(request, "shopping/shopping.html", context)


@login_required
def edit_shopping(request, shopping_id):
    shopping = get_object_or_404(Shopping, id=shopping_id, user=request.user)
    shops = Shop.objects.all()

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
                item.save()
            return redirect("shopping")
        return redirect("edit_shopping", shopping_id=shopping.id)


    context = {"shopping": shopping, 'shops': shops}

    return render(request, "shopping/edit_shopping.html", context)


@login_required
def make_shopping(request):
    shops = Shop.objects.all()
    categories = ProductCategory.objects.all().order_by('name')
    main_categories = MainCategory.objects.all()
    all_products = Product.objects.all().order_by('name')

    shopping_lists = ShoppingList.objects.filter(user=request.user, executed=True).order_by('-date_generated')[:5]

    selected_category_id = request.GET.get("category")

    # load from shopping list
    selected_list_id = request.GET.get("list")
    prefill_data = []

    if selected_list_id:
        try:
            shopping_list = ShoppingList.objects.get(id=selected_list_id, user=request.user)
            for item_name in shopping_list.items:
                product = Product.objects.filter(name=item_name).first()
                if product:
                    last_price = 0.00
                    shoppings = Shopping.objects.filter(user=request.user)
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
        shop_id = request.POST["shop_id"]
        date = request.POST["date"]
        selected_products = json.loads(request.POST["selected_products"])

        shop = Shop.objects.get(id=shop_id)
        shopping = Shopping.objects.create(user=request.user, date=date, shop=shop)

        for product_data in selected_products:
            product = Product.objects.get(id=product_data["product_id"])
            quantity = Decimal(product_data["quantity"])
            price = Decimal(product_data["price"])
            discount = Decimal(product_data["discount"] if product_data["discount"] else 0)
            amount = quantity * price - discount

            ShoppingProduct.objects.create(
                shopping=shopping, product=product, quantity=quantity, price=price,
                discount=discount, amount=amount
            )

            inventory_product, created = InventoryProduct.objects.get_or_create(
                user=request.user, product=product, category=product.category,
                defaults={"quantity": 0, "amount": 0}
            )
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
        new_product = Product.objects.create(name=product_name, calories=calories, category=category)

        return JsonResponse({"id": new_product.id, "name": new_product.name})

