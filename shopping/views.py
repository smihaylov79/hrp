from decimal import Decimal

from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import *
from inventory.models import InventoryProduct, UserProductCategory


def shopping_list(request):
    categories = ProductCategory.objects.all()
    main_categories = MainCategory.objects.all()
    products = Product.objects.all()

    for product in products:
        product.price_eur = round(product.price / Decimal('1.95583'), 2)

    return render(request, "shopping/shopping.html", {
        "products": products,
        "categories": categories,
        "main_categories": main_categories,
    })


@login_required
def add_to_basket(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    basket, created = Basket.objects.get_or_create(user=request.user)

    # Check if the product is already in the basket
    if request.method == "POST":
        quantity = Decimal(request.POST.get('quantity', '1.000'))  # Convert input to decimal

        basket_item, created = BasketItem.objects.get_or_create(basket=basket, product=product)
        basket_item.quantity += quantity if not created else quantity  # Update quantity
        basket_item.save()

    return redirect('shopping')


@login_required
def basket_view(request):
    basket, created = Basket.objects.get_or_create(user=request.user)
    items = basket.basketitem_set.all()  # Get all items in the basket
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

        # Update quantity and amount
        inventory_item.quantity += item.quantity
        inventory_item.amount += item.quantity * Decimal(str(item.product.price))

        # Recalculate average price


        inventory_item.save()
        inventory_item.calculate_average_price()

    items.delete()  # Clear basket

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
def save_shopping(request):
    if request.method == "POST":
        shop_id = request.POST["shop_id"]
        date = request.POST["date"]
        product_ids = request.POST.getlist("product_id[]")
        quantities = request.POST.getlist("quantity[]")
        prices = request.POST.getlist("price[]")
        discounts = request.POST.getlist("discount[]")

        # Get selected shop
        shop = Shop.objects.get(id=shop_id)

        # Create shopping entry
        shopping = Shopping.objects.create(user=request.user, date=date, shop=shop)

        # Save each product entry
        for i in range(len(product_ids)):
            product = Product.objects.get(id=product_ids[i])
            quantity = Decimal(quantities[i])
            price = Decimal(prices[i])
            discount = Decimal(discounts[i])
            amount = quantity * price - discount

            ShoppingProduct.objects.create(
                shopping=shopping, product=product, quantity=quantity, price=price,
                discount=discount, amount=amount
            )
            user_category, created = UserProductCategory.objects.get_or_create(user=request.user, product_category=product.category,
                                                                               defaults={'direct_planning': False, 'daily_consumption': 0.000,
                                                                               'minimum_quantity':0.000}
            )
            # Update inventory
            inventory_product, created = InventoryProduct.objects.get_or_create(
                user=request.user, product=product, category=product.category,
                defaults={"quantity": 0, "amount": 0}
            )
            inventory_product.quantity += quantity
            inventory_product.amount += amount
            inventory_product.calculate_average_price()
            inventory_product.save()

        return redirect("shopping")

    return redirect("create_shopping")


def add_product(request):
    if request.method == "POST":
        category_id = request.POST.get("category_id")
        product_name = request.POST.get("new_product_name")
        price = request.POST.get("new_price")

        category = ProductCategory.objects.get(id=category_id)

        # Create new product
        new_product = Product.objects.create(name=product_name, price=price, category=category)

        return JsonResponse({"id": new_product.id, "name": new_product.name})