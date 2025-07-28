from datetime import date
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.safestring import mark_safe

from shopping.models import *
from .models import *
from taskmanager.models import Task


@login_required
def inventory_list(request):
    user = request.user
    household = user.household

    if household:
        user_categories = HouseholdProductCategory.objects.filter(household=household)
        inventory_items = HouseholdInventoryProduct.objects.filter(household=household).order_by('product__name')
    else:
        user_categories = UserProductCategory.objects.filter(user=request.user)
        inventory_items = InventoryProduct.objects.filter(user=request.user).order_by('product__name')

    category_filter = request.GET.get("category")
    search_query = request.GET.get("search")
    inventory_filter = request.GET.get("inventory_only", "true")
    total_amount = inventory_items.aggregate(total_value=Sum('amount'))['total_value']

    if inventory_filter == "true":
        inventory_items = inventory_items.filter(inventory_related=True)

    else:
        inventory_items = inventory_items.filter(inventory_related=False)

    if category_filter and category_filter.strip() != "":
        inventory_items = inventory_items.filter(category_id=category_filter).order_by('id')

    if search_query and search_query.strip() != "":
        inventory_items = inventory_items.filter(product__name__icontains=search_query)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        items_data = [{
            "id": item.id,
            "name": item.product.name,
            "average_price": float(item.average_price),
            "quantity": float(item.quantity),
            "amount": float(item.amount),
            "daily_consumption": float(item.daily_consumption),
            "minimum_quantity": float(item.minimum_quantity),
            "inventory_related": item.inventory_related
        } for item in inventory_items]

        return JsonResponse({"items": items_data})

    return render(request, "inventory/inventory.html", {
        "inventory_items": inventory_items,
        "user_categories": user_categories,
        'household': household,
        'total_amount': total_amount,
    })


def update_inventory(request):
    if request.method == "POST":
        user = request.user
        household = user.household
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

                if field == "inventory_related":
                    data[product_id][field] = value == "true"
                else:
                    try:
                        data[product_id][field] = float(value)
                    except ValueError:
                        data[product_id][field] = 0.0

        if household:
            HouseholdInventoryProduct.bulk_update_inventory(data)
        else:
            InventoryProduct.bulk_update_inventory(data)

        return redirect("inventory")

    return redirect("inventory")


def user_category_settings(request):
    user = request.user
    household = user.household

    if household:
        user_categories = HouseholdProductCategory.objects.filter(household=household)
    else:
        user_categories = UserProductCategory.objects.filter(user=user)
    if request.method == "POST":
        for category in user_categories:
            category.direct_planning = request.POST.get(f"direct_planning_{category.id}") == "on"
            category.daily_consumption = request.POST.get(f"daily_consumption_{category.id}",
                                                          category.daily_consumption)
            category.minimum_quantity = request.POST.get(f"minimum_quantity_{category.id}", category.minimum_quantity)
            category.save()

        return redirect("user_category_settings")

    context = {
        "user_categories": user_categories
    }

    return render(request, "inventory/user_category_settings.html", context)


@login_required
def generate_shopping_list(request):
    user = request.user
    household = user.household
    today = date.today()

    if household:
        last_list = HouseholdShoppingList.objects.filter(household=household).order_by("-date_generated").first()
        days_since_last = (today - last_list.date_generated).days if last_list else 7

        inventory_items = HouseholdInventoryProduct.objects.filter(household=household)
        shopping_list = HouseholdShoppingList.objects.create(household=household, items=[])

        user_direct_categories = HouseholdProductCategory.objects.filter(household=household, direct_planning=True)
        user_indirect_categories = HouseholdProductCategory.objects.filter(household=household, direct_planning=False)

    else:
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

    link = reverse("shopping_list_view", args=[shopping_list.id])

    if household:
        household_members = CustomUser.objects.filter(household=household)
        description = mark_safe(f'Списък за пазаруване, генериран от {shopping_list.household.name} -> '
                                f'<a href="{link}">Отиди на списъка</a>')
        for member in household_members:
            Task.objects.create(
                title=f'Пазаруване {shopping_list.date_generated}',
                description=description,
                due_date=shopping_list.date_generated,
                user=member,
            )
    else:
        Task.objects.create(
            title=f'Пазаруване {shopping_list.date_generated}',
            description=f'Списък за пазаруване, генериран от {shopping_list.user.first_name}',
            due_date=shopping_list.date_generated,
            user=shopping_list.user
        )

    return redirect("shopping_list_view", list_id=shopping_list.id)


@login_required
def update_shopping_list(request, list_id):
    user = request.user
    household = user.household
    if household:
        shopping_list = HouseholdShoppingList.objects.get(id=list_id, household=household)
    else:
        shopping_list = ShoppingList.objects.get(id=list_id, user=user)

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
    user = request.user
    household = user.household
    if household:
        shopping_list = HouseholdShoppingList.objects.get(id=list_id, household=household)
    else:
        shopping_list = ShoppingList.objects.get(id=list_id, user=user)
    shopping_list.executed = True
    shopping_list.save()
    return redirect("all_shopping_lists")


@login_required
def execute_recipe_shopping_list(request, list_id):
    user = request.user
    household = user.household
    if household:
        shopping_list = HouseholdRecipeShoppingList.objects.get(id=list_id, household=household)
    else:
        shopping_list = RecipeShoppingList.objects.get(id=list_id, user=user)
    shopping_list.executed = True
    shopping_list.save()
    return redirect("all_shopping_lists")


@login_required
def shopping_list_view(request, list_id):
    user = request.user
    household = user.household
    if household:
        shopping_list = get_object_or_404(HouseholdShoppingList, id=list_id, household=household)
    else:
        shopping_list = get_object_or_404(ShoppingList, id=list_id, user=user)

    return render(request, "inventory/shopping_list.html", {"shopping_list": shopping_list})


@login_required
def all_shopping_lists(request):
    user = request.user
    household = user.household
    if household:
        standard_shopping_lists = HouseholdShoppingList.objects.filter(household=household).order_by("-date_generated")
        recipe_shopping_lists = HouseholdRecipeShoppingList.objects.filter(household=household)
    else:
        standard_shopping_lists = ShoppingList.objects.filter(user=user).order_by("-date_generated")
        recipe_shopping_lists = RecipeShoppingList.objects.filter(user=user)

    context = {
        "shopping_lists": standard_shopping_lists, "recipe_shopping_lists": recipe_shopping_lists
    }

    return render(
        request, "inventory/all_shopping_lists.html", context
    )


@login_required
def recipe_shopping_list_view(request, list_id):
    user = request.user
    household = user.household
    if household:
        recipe_list = get_object_or_404(HouseholdRecipeShoppingList, id=list_id, household=household)
    else:
        recipe_list = get_object_or_404(RecipeShoppingList, id=list_id, user=user)

    return render(request, "inventory/recipe_shopping_list.html", {"recipe_list": recipe_list})
