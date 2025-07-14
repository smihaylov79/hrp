from datetime import date
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
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
def execute_shopping_list(request, list_id):
    shopping_list = ShoppingList.objects.get(id=list_id, user=request.user)
    shopping_list.executed = True
    shopping_list.save()
    return redirect("all_shopping_lists")


@login_required
def execute_recipe_shopping_list(request, list_id):
    shopping_list = RecipeShoppingList.objects.get(id=list_id, user=request.user)
    shopping_list.executed = True
    shopping_list.save()
    return redirect("all_shopping_lists")



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
def recipe_shopping_list_view(request, list_id):
    recipe_list = get_object_or_404(RecipeShoppingList, id=list_id, user=request.user)

    return render(request, "inventory/recipe_shopping_list.html", {"recipe_list": recipe_list})



