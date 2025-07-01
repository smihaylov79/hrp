from datetime import date
from decimal import Decimal
from email.mime.text import MIMEText
import os
import json

from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db.models import Sum, Avg
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
import smtplib


from shopping.models import ShoppingProduct, Shop, Shopping, ShoppingList, RecipeShoppingList, MainCategory
from .models import *

@login_required
def inventory_list(request):
    user_categories = UserProductCategory.objects.filter(user=request.user)
    inventory_items = InventoryProduct.objects.filter(user=request.user).order_by('product__name')

    category_filter = request.GET.get("category")
    search_query = request.GET.get("search")

    if category_filter and category_filter.strip() != "":
        inventory_items = inventory_items.filter(category_id=category_filter).order_by('id')

    if search_query and search_query.strip() != "":
        inventory_items = inventory_items.filter(product__name__icontains=search_query)

    return render(request, "inventory/inventory.html", {
        "inventory_items": inventory_items,
        "user_categories": user_categories,
    })

def update_inventory(request):
    if request.method == "POST":
        data = {}

        for key, value in request.POST.items():
            if "_" in key:
                parts = key.rsplit("_", 1)
                if len(parts) == 2 and parts[1].isdigit():
                    field, product_id = parts
                else:
                    continue
                if product_id not in data:
                    data[product_id] = {}

                data[product_id][field] = float(value)

        InventoryProduct.bulk_update_inventory(data)

        return redirect("inventory")

    return redirect("inventory")


def user_category_settings(request):
    user_categories = UserProductCategory.objects.filter(user=request.user)
    if request.method == "POST":
        for category in user_categories:
            category.direct_planning = request.POST.get(f"direct_planning_{category.id}") == "on"
            category.daily_consumption = request.POST.get(f"daily_consumption_{category.id}",
                                                          category.daily_consumption)
            category.minimum_quantity = request.POST.get(f"minimum_quantity_{category.id}", category.minimum_quantity)
            category.save()

        return redirect("user_category_settings")

    return render(request, "inventory/user_category_settings.html", {"user_categories": user_categories})



def inventory_reports(request):
    user_categories = UserProductCategory.objects.filter(user=request.user)

    main_categories = MainCategory.objects.all()

    main_category_name = ""

    user_shops = Shop.objects.filter(id__in=Shopping.objects.filter(user=request.user).values("shop")).distinct()

    main_category_filter = request.GET.get("main_category", "")
    category_filter = request.GET.get("category")
    date_filter = request.GET.get("date")
    shop_filter = request.GET.get("shop")

    selected_shops = request.GET.getlist("shops")

    shopping_data = ShoppingProduct.objects.filter(shopping__user=request.user)

    if main_category_filter and main_category_filter.strip():
        shopping_data = shopping_data.filter(product__category_id__main_category_id=main_category_filter)
        main_category = main_categories.filter(id=main_category_filter).first()
        main_category_name = main_category.name

    if category_filter and category_filter.strip():
        shopping_data = shopping_data.filter(product__category_id=category_filter)

    if date_filter and date_filter.strip():
        shopping_data = shopping_data.filter(shopping__date=date_filter)

    if shop_filter and shop_filter.strip():
        shopping_data = shopping_data.filter(shopping__shop_id=shop_filter)

    total_spent = round(shopping_data.aggregate(total=Sum("amount"))["total"] or 0, 2)

    avg_price_changes = shopping_data.values("product__name").annotate(avg_price=Avg("price"))
    for item in avg_price_changes:
        item["avg_price"] = round(item["avg_price"], 2)

    shop_price_changes = []
    for shop in user_shops:
        shop_avg_prices = shopping_data.filter(shopping__shop=shop).values("product__name").annotate(
            shop_avg_price=Avg("price"))

        shop_data = {
            "shop_name": shop.name,
            "shop_id": shop.id,
            "prices": {item["product__name"]: round(item["shop_avg_price"], 2) for item in shop_avg_prices}
        }

        shop_price_changes.append(shop_data)


    ## for the chart with highcharts
    main_category_spending = shopping_data.values("product__category__main_category__name").annotate(
        total_spent=Sum("amount"))
    subcategory_spending = shopping_data.values("product__category__name").annotate(total_spent=Sum("amount"))

    main_chart_data = [{"name": entry["product__category__main_category__name"], "y": float(entry["total_spent"])}
                       for entry in main_category_spending]
    sub_chart_data = [{"name": entry["product__category__name"], "y": float(entry["total_spent"])}
                      for entry in subcategory_spending]

    context = {
        "shopping_data": shopping_data,
        "total_spent": float(total_spent),
        "avg_price_changes": avg_price_changes,
        "shop_price_changes": shop_price_changes,
        "user_categories": user_categories,
        "user_shops": user_shops,
        "selected_shops": selected_shops,
        "main_chart_data": json.dumps(main_chart_data),
        "sub_chart_data": json.dumps(sub_chart_data),
        "category_filter": category_filter,
        "date_filter": date_filter,
        "shop_filter": shop_filter,
        "main_categories": main_categories,
        "main_category_filter": main_category_filter,
        "main_category_name": main_category_name,
    }

    return render(request, "inventory/reports.html", context)


def product_price_history(request):
    user = request.user
    products = Product.objects.filter(
        shoppingproduct__shopping__user=user).distinct()
    selected_product_id = request.GET.get("product")
    price_data = []

    if selected_product_id:
        product = get_object_or_404(Product, id=selected_product_id)

        price_changes = ShoppingProduct.objects.filter(shopping__user=user, product=product) \
            .values("shopping__date").annotate(avg_price=Avg("price")).order_by("shopping__date")

        price_data = [{"date": entry["shopping__date"].strftime("%Y-%m-%d"), "price": float(entry["avg_price"])} for entry in price_changes]

    context = {
        "products": products,
        "selected_product_id": selected_product_id,
        "price_data": json.dumps(price_data) if price_data else "[]"
    }

    return render(request, "inventory/price_history.html", context)


@login_required
def generate_shopping_list(request):
    user = request.user
    today = date.today()

    last_list = ShoppingList.objects.filter(user=user).order_by("-date_generated").first()
    days_since_last = (today - last_list.date_generated).days if last_list else 7

    inventory_items = InventoryProduct.objects.filter(user=user)
    shopping_list = ShoppingList.objects.create(user=user, items=[])

    user_direct_categories = UserProductCategory.objects.filter(user=user, direct_planning=True)
    user_indirect_categories = UserProductCategory.objects.filter(user=user, direct_planning=False)

    for category in user_direct_categories:
        category_items = inventory_items.filter(category=category.product_category)
        total_stock = sum(item.quantity for item in category_items)
        total_consumption = category.daily_consumption * days_since_last

        if total_stock - total_consumption < category.minimum_quantity:
            shopping_list.items.append(category.product_category.name)

        for product in category_items:
            if product.quantity < total_consumption:
                total_consumption -= product.quantity
                product.quantity = 0
                product.amount = 0
                product.average_price = 0
                product.save()
            else:
                product.quantity -= total_consumption
                product.amount -= total_consumption * product.average_price
                product.calculate_average_price()
                product.save()
                total_consumption = 0
                break
    for category in user_indirect_categories:
        category_items = inventory_items.filter(category=category.product_category)
        for product in category_items:
            total_consumption = product.daily_consumption * days_since_last
            if product.quantity - total_consumption < product.minimum_quantity and product.minimum_quantity > 0:
                shopping_list.items.append(product.product.name)

            if product.quantity <= total_consumption:
                product.quantity = 0
                product.amount = 0
                product.average_price = 0
                product.save()
            else:
                product.quantity -= total_consumption
                product.amount -= total_consumption * product.average_price
                product.calculate_average_price()
                product.save()
                total_consumption = 0

    shopping_list.save()
    return redirect("shopping_list_view", list_id=shopping_list.id)


@login_required
def update_shopping_list(request, list_id):
    shopping_list = ShoppingList.objects.get(id=list_id, user=request.user)

    if request.method == "POST":
        if "add_item" in request.POST:
            new_item = request.POST.get("new_item")
            if new_item and new_item not in shopping_list.items:
                shopping_list.items.append(new_item)

        if "remove_item" in request.POST:
            remove_item = request.POST.get("remove_item")
            shopping_list.items = [item for item in shopping_list.items if item != remove_item]

        shopping_list.save()

    return redirect("shopping_list_view", list_id=list_id)


@login_required
def send_shopping_list(request, list_id):
    shopping_list = ShoppingList.objects.get(id=list_id, user=request.user)
    new_date = shopping_list.date_generated
    items = shopping_list.items
    email = request.user.email
    password = os.getenv('EMAIL_PASSWORD')
    smtp_server = os.getenv('SMTP_SERVER')
    login = os.getenv('LOGIN_USER')


    server = smtplib.SMTP_SSL(smtp_server, 465)
    server.login(login, password)
    msg = MIMEText('\n'.join(items))

    msg['Subject'] = f'Списък за пазаруване: {new_date}'
    msg['From'] = login
    msg['To'] = email

    server.sendmail(
        login,
        [email],
        msg.as_string()
    )

    shopping_list.sent = True
    shopping_list.save()

    return redirect("shopping_list_view", list_id=list_id)




@login_required
def shopping_list_view(request, list_id):
    shopping_list = get_object_or_404(ShoppingList, id=list_id, user=request.user)

    return render(request, "inventory/shopping_list.html", {"shopping_list": shopping_list})


@login_required
def all_shopping_lists(request):
    shopping_lists = ShoppingList.objects.filter(user=request.user).order_by("-date_generated")

    return render(request, "inventory/all_shopping_lists.html", {"shopping_lists": shopping_lists})


@login_required
def all_shopping_lists(request):
    standard_shopping_lists = ShoppingList.objects.filter(user=request.user).order_by("-date_generated")
    recipe_shopping_lists = RecipeShoppingList.objects.filter(user=request.user)

    return render(
        request,
        "inventory/all_shopping_lists.html",
        {"shopping_lists": standard_shopping_lists, "recipe_shopping_lists": recipe_shopping_lists}
    )

@login_required
def send_recipe_shopping_list(request, list_id):
    recipe_list = RecipeShoppingList.objects.get(id=list_id, user=request.user)
    recipe_name = recipe_list.recipe_name
    items = recipe_list.items
    email = request.user.email

    password = os.getenv('EMAIL_PASSWORD')
    smtp_server = os.getenv('SMTP_SERVER')
    login = os.getenv('LOGIN_USER')

    server = smtplib.SMTP_SSL(smtp_server, 465)
    server.login(login, password)
    msg = MIMEText('\n'.join(items))

    msg['Subject'] = f'Списък за пазаруване за рецепта: {recipe_name}'
    msg['From'] = login
    msg['To'] = email

    server.sendmail(
        login,
        [email],
        msg.as_string()
    )

    recipe_list.sent = True
    recipe_list.save()

    return redirect("recipe_shopping_list_view", list_id=list_id)


@login_required
def recipe_shopping_list_view(request, list_id):
    recipe_list = get_object_or_404(RecipeShoppingList, id=list_id, user=request.user)

    return render(request, "inventory/recipe_shopping_list.html", {"recipe_list": recipe_list})
