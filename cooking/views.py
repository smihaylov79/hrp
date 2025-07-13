from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required

from cooking.models import *
from inventory.models import InventoryProduct
from shopping.models import RecipeShoppingList, ProductCategory


# Create your views here.

def recipe_list(request):
    category_name = request.GET.get('category', 'all')
    recipes = Recipe.objects.all()
    categories = RecipeCategory.objects.all()
    all_products = Product.objects.all()

    ingredient = request.GET.get('ingredient', 'all')

    if ingredient != 'all':
        recipes = recipes.filter(ingredients__id=ingredient)

    user = None
    times_cooked = 0
    if request.user.is_authenticated:
        user = request.user


    if category_name != 'all':
        recipes = recipes.filter(category__name=category_name)

    user_inventory = InventoryProduct.objects.filter(user=user)
    product_price_map = {item.product.id: item.average_price for item in user_inventory}
    product_quantity_map = {item.product.id: item.quantity for item in user_inventory}

    for recipe in recipes:
        recipe.user_cost = round(sum(product_price_map.get(ingredient.product.id, 0) * ingredient.quantity
                               for ingredient in recipe.recipe_ingredients.all()), 2)
        recipe.user_availability = all(product_quantity_map.get(ingredient.product.id, 0) >= ingredient.quantity
                                       for ingredient in recipe.recipe_ingredients.all())
        recipe.ingredients_list = RecipeIngredient.objects.filter(recipe=recipe)
        recipe.user_availability_status = recipe.check_availability(user)

        recipe.times_cooked = RecipeTimesCooked.objects.filter(user=user, recipe=recipe).count()

    top_ids = sorted(recipes, key=lambda x: x.times_cooked, reverse=True)[:6]
    top_ids_set = set(r.id for r in top_ids)

    for recipe in recipes:
        recipe.is_top = recipe.id in top_ids_set
        recipe.category_name = recipe.category.name.lower()

    context = {'recipes': recipes,
               'user_inventory': {item.product.id: item.quantity for item in user_inventory},
               'categories': categories,
               'selected_category': category_name,
               'times_cooked': times_cooked,
               'prducts': all_products,
               'ingredient': ingredient,
               }
    return render(request, 'cooking/recipe_list.html', context)


@login_required
def create_recipe(request):
    products = Product.objects.all()
    categories = RecipeCategory.objects.all()
    product_categories = ProductCategory.objects.all()

    return render(request, "cooking/create_recipe.html", {
        "products": products,
        "categories": categories,
        'product_categories': product_categories,
    })


@login_required
def save_recipe(request):
    if request.method == "POST":
        recipe_name = request.POST["name"]
        category_id = request.POST["category_id"]
        time_to_prepare = request.POST["time_to_prepare"]
        instructions = request.POST["instructions"]
        url_link = request.POST.get("url_link", None)

        product_ids = request.POST.getlist("product_id[]")
        quantities = request.POST.getlist("quantity[]")
        units = request.POST.getlist("unit[]")

        category = RecipeCategory.objects.get(id=category_id)

        recipe = Recipe.objects.create(
            name=recipe_name,
            category=category,
            time_to_prepare=time_to_prepare,
            instructions=instructions,
            url_link=url_link
        )

        for i in range(len(product_ids)):
            product = Product.objects.get(id=product_ids[i])
            quantity = Decimal(quantities[i])
            unit = units[i]

            RecipeIngredient.objects.create(
                recipe=recipe,
                product=product,
                quantity=quantity,
                unit=unit
            )

        return redirect("recipe_list")

    return redirect("create_recipe")


@login_required
def cook_recipe(request, recipe_id):
    recipe = Recipe.objects.get(id=recipe_id)
    user_inventory = InventoryProduct.objects.filter(user=request.user)
    product_quantity_map = {item.product.id: item.quantity for item in user_inventory}


    for ingredient in RecipeIngredient.objects.filter(recipe=recipe):
        inventory_product = user_inventory.filter(product=ingredient.product).first()
        if inventory_product:
            if inventory_product.quantity > ingredient.quantity:
                inventory_product.quantity -= ingredient.quantity
                inventory_product.amount -= ingredient.quantity * inventory_product.average_price
                inventory_product.calculate_average_price()
                inventory_product.save()
            else:
                inventory_product.quantity = 0
                inventory_product.amount = 0
                inventory_product.calculate_average_price()
                inventory_product.save()

    RecipeTimesCooked.objects.create(user=request.user, recipe=recipe)

    return redirect("recipe_list")


@login_required
def generate_recipe_shopping_list(request, recipe_id):
    recipe = Recipe.objects.get(id=recipe_id)
    user_inventory = InventoryProduct.objects.filter(user=request.user)
    product_quantity_map = {item.product.id: item.quantity for item in user_inventory}

    ingredients = RecipeIngredient.objects.filter(recipe=recipe)

    missing_products = [
        ingredient.product.name
        for ingredient in ingredients
        if product_quantity_map.get(ingredient.product.id, 0) < ingredient.quantity
    ]

    if missing_products:
        RecipeShoppingList.objects.create(user=request.user, recipe_name=recipe.name, items=missing_products)
        messages.success(request, f"Списъкът с липсващи продукти за {recipe.name} е успешно генериран!")
    else:
        messages.info(request, f"Всички продукти за {recipe.name} са налични, няма нужда от пазаруване.")

    return redirect("recipe_list")


def recipe_view(request, recipe_id):
    user = None
    times_cooked = 0
    last_cooked = ''
    if request.user.is_authenticated:
        user = request.user
        recipe = Recipe.objects.get(id=recipe_id)
        cooking_history = RecipeTimesCooked.objects.filter(user=user, recipe=recipe).order_by('date')
        if cooking_history:
            times_cooked = cooking_history.count()
            last_cooked = cooking_history.last().date

    recipe = get_object_or_404(Recipe, id=recipe_id)
    user_inventory = InventoryProduct.objects.filter(user=user)
    product_price_map = {item.product.id: item.average_price for item in user_inventory}
    product_quantity_map = {item.product.id: item.quantity for item in user_inventory}

    recipe.user_cost = round(sum(product_price_map.get(ingredient.product.id, 0) * ingredient.quantity
                                     for ingredient in recipe.recipe_ingredients.all()), 2)
    recipe.user_availability = all(product_quantity_map.get(ingredient.product.id, 0) >= ingredient.quantity
                                       for ingredient in recipe.recipe_ingredients.all())
    recipe.ingredients_list = RecipeIngredient.objects.filter(recipe=recipe)
    context = {
        "recipe": recipe,
        'user_inventory': {item.product.id: item.quantity for item in user_inventory},
        'user': user,
        'times_cooked': times_cooked,
        'last_cooked' :last_cooked

    }
    return render(request, "cooking/recipe_view.html", context)


