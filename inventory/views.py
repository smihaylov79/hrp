from datetime import date
from decimal import Decimal
from email.mime.text import MIMEText

from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db.models import Sum, Avg
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
import smtplib

from shopping.models import ShoppingProduct, Shop, Shopping, ShoppingList, RecipeShoppingList
from .models import *

@login_required
def inventory_list(request):
    user_categories = UserProductCategory.objects.filter(user=request.user)
    inventory_items = InventoryProduct.objects.filter(user=request.user)

    category_filter = request.GET.get("category")
    search_query = request.GET.get("search")

    # Apply category filter separately
    if category_filter and category_filter.strip() != "":
        inventory_items = inventory_items.filter(category_id=category_filter).order_by('id')

    # Apply search filter separately
    if search_query and search_query.strip() != "":
        inventory_items = inventory_items.filter(product__name__icontains=search_query)

    return render(request, "inventory/inventory.html", {
        "inventory_items": inventory_items,
        "user_categories": user_categories,  # Ensure categories are available
    })

def update_inventory(request):
    if request.method == "POST":
        data = {}  # Store updates per product

        for key, value in request.POST.items():
            if "_" in key:
                parts = key.rsplit("_", 1)  # Splits at the **last** underscore
                if len(parts) == 2 and parts[1].isdigit():  # Ensures valid numeric ID
                    field, product_id = parts
                else:
                    continue  # Skip invalid keys
                if product_id not in data:
                    data[product_id] = {}  # Initialize sub-dictionary

                data[product_id][field] = float(value)  # Convert input to float

        # Apply bulk updates
        InventoryProduct.bulk_update_inventory(data)

        return redirect("inventory")  # Redirect after saving

    return redirect("inventory")  # Fallback redirect


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
    # Get all categories associated with the user
    user_categories = UserProductCategory.objects.filter(user=request.user)

    # Get all shops the user has made purchases from
    user_shops = Shop.objects.filter(id__in=Shopping.objects.filter(user=request.user).values("shop")).distinct()
    # Filter options
    category_filter = request.GET.get("category")
    date_filter = request.GET.get("date")
    shop_filter = request.GET.get("shop")

    # Get base shopping data
    shopping_data = ShoppingProduct.objects.filter(shopping__user=request.user)

    if category_filter and category_filter.strip() != "":
        shopping_data = shopping_data.filter(product__category_id=category_filter)

    if date_filter and date_filter.strip() != "":
        shopping_data = shopping_data.filter(shopping__date=date_filter)

    if shop_filter and shop_filter.strip() != "":
        shopping_data = shopping_data.filter(shopping__shop_id=shop_filter)

    # Aggregate data
    total_spent = round(shopping_data.aggregate(total=Sum("amount"))["total"], 2) or 0
    avg_price_changes = shopping_data.values("product__name").annotate(avg_price=Avg("price"))
    for item in avg_price_changes:
        item["avg_price"] = round(item["avg_price"], 2)

    context = {
        "shopping_data": shopping_data,
        "total_spent": total_spent,
        "avg_price_changes": avg_price_changes,
        "user_categories": user_categories,  # Pass categories
        "user_shops": user_shops,  # Pass shops
    }

    return render(request, "inventory/reports.html", context)

@login_required
def generate_shopping_list(request):
    user = request.user
    today = date.today()

    last_list = ShoppingList.objects.filter(user=user).order_by("-date_generated").first()
    days_since_last = (today - last_list.date_generated).days if last_list else 7  # Default: 7 days

    inventory_items = InventoryProduct.objects.filter(user=user)
    shopping_list = ShoppingList.objects.create(user=user, items=[])

    # Handle direct planning categories first
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
            if product.quantity - total_consumption < product.minimum_quantity:
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


    server = smtplib.SMTP_SSL('smtp.abv.bg', 465)
    server.login('shopping_tracker_app@abv.bg', 'c2hvvGKTKgVH9C_')
    msg = MIMEText('\n'.join(items))

    msg['Subject'] = f'Списък за пазаруване: {new_date}'
    msg['From'] = 'shopping_tracker_app@abv.bg'  # Ensure this matches EMAIL_HOST_USER
    msg['To'] = email

    server.sendmail(
        'shopping_tracker_app@abv.bg',
        ['stoyan.mihaylov@live.com', email],
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

    server = smtplib.SMTP_SSL('smtp.abv.bg', 465)
    server.login('shopping_tracker_app@abv.bg', 'c2hvvGKTKgVH9C_')
    msg = MIMEText('\n'.join(items))

    msg['Subject'] = f'Списък за пазаруване за рецепта: {recipe_name}'
    msg['From'] = 'shopping_tracker_app@abv.bg'
    msg['To'] = email

    server.sendmail(
        'shopping_tracker_app@abv.bg',
        ['stoyan.mihaylov@live.com', email],
        msg.as_string()
    )

    recipe_list.sent = True
    recipe_list.save()

    return redirect("recipe_shopping_list_view", list_id=list_id)


@login_required
def recipe_shopping_list_view(request, list_id):
    recipe_list = get_object_or_404(RecipeShoppingList, id=list_id, user=request.user)

    return render(request, "inventory/recipe_shopping_list.html", {"recipe_list": recipe_list})
