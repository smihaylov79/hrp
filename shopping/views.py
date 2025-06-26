from decimal import Decimal
import json
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Case, When, IntegerField
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
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
def add_to_basket(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    basket, created = Basket.objects.get_or_create(user=request.user)

    if request.method == "POST":
        quantity = Decimal(request.POST.get('quantity', '1.000'))

        basket_item, created = BasketItem.objects.get_or_create(basket=basket, product=product)
        basket_item.quantity += quantity if not created else quantity
        basket_item.save()

    return redirect('shopping')


@login_required
def basket_view(request):
    basket, created = Basket.objects.get_or_create(user=request.user)
    items = basket.basketitem_set.all()
    return render(request, "shopping/basket.html", {"items": items})


@login_required
def update_basket(request, item_id):
    item = BasketItem.objects.get(id=item_id)
    if request.method == "POST":
        item.quantity = request.POST.get('quantity')
        item.save()
    return redirect('basket')


@login_required
def remove_from_basket(request, item_id):
    item = BasketItem.objects.get(id=item_id)
    item.delete()
    return redirect('basket')


@login_required
def checkout(request):
    basket = Basket.objects.get(user=request.user)
    items = basket.basketitem_set.all()

    for item in items:
        inventory_item, created = InventoryProduct.objects.get_or_create(
            user=request.user,
            product=item.product,
            defaults={'quantity': Decimal('0.000'), 'amount': Decimal('0.00')}
        )

        inventory_item.quantity += item.quantity
        inventory_item.amount += item.quantity * Decimal(str(item.product.price))

        inventory_item.save()
        inventory_item.calculate_average_price()

    items.delete()

    return redirect('inventory')


@login_required
def create_shopping(request):
    shops = Shop.objects.all()
    products = Product.objects.all()
    categories = ProductCategory.objects.all()
    main_categories = MainCategory.objects.all()
    return render(request, "shopping/create_shopping.html", {
        "shops": shops,
        "products": products,
        "categories": categories,
        "main_categories": main_categories,
    })


@login_required
def make_shopping(request):
    shops = Shop.objects.all()
    categories = ProductCategory.objects.all().order_by('name')
    main_categories = MainCategory.objects.all()

    selected_category_id = request.GET.get("category")

    user_orders = ShoppingProduct.objects.filter(shopping__user=request.user) \
        .values("product_id") \
        .annotate(purchase_count=Count("product_id")) \
        .order_by("-purchase_count")

    ordered_product_ids = [entry["product_id"] for entry in user_orders]
    purchased_products = Product.objects.filter(id__in=ordered_product_ids).order_by(
        Case(
            *[When(id=pid, then=pos) for pos, pid in enumerate(ordered_product_ids)],
            output_field=IntegerField()
        )
    )

    if selected_category_id:
        purchased_products = purchased_products.filter(category_id=selected_category_id)

    other_products = Product.objects.exclude(id__in=ordered_product_ids)
    if selected_category_id:
        other_products = other_products.filter(category_id=selected_category_id)


    all_products = list(purchased_products) + list(other_products)

    paginator = Paginator(all_products, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "shops": shops,
        "products": page_obj,
        "categories": categories,
        "main_categories": main_categories,
        "selected_category": selected_category_id
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