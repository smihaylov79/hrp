from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required

from cooking.models import *
from inventory.models import InventoryProduct
from shopping.models import RecipeShoppingList


# Create your views here.
@login_required
def recipe_list(request):
    category_name = request.GET.get('category', 'all')
    recipes = Recipe.objects.all()
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

    paginator = Paginator(recipes, 6)  # 6 recipes per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {'recipes': recipes,
               'user_inventory': {item.product.id: item.quantity for item in user_inventory},
               'page_obj': page_obj,
               'categories': RecipeCategory.objects.all(),
               'selected_category': category_name,
               }
    return render(request, 'cooking/recipe_list.html', context)


def create_recipe(request):
    products = Product.objects.all()  # ✅ Get all products
    categories = RecipeCategory.objects.all()  # ✅ Get all recipe categories

    return render(request, "cooking/create_recipe.html", {
        "products": products,
        "categories": categories  # ✅ Pass them to the template
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

        # Get recipe category
        category = RecipeCategory.objects.get(id=category_id)

        # Create recipe entry
        recipe = Recipe.objects.create(
            name=recipe_name,
            category=category,
            time_to_prepare=time_to_prepare,
            instructions=instructions,
            url_link=url_link
        )

        # ✅ Loop through all submitted ingredients and save them
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

    # Check if user has all required ingredients
    for ingredient in RecipeIngredient.objects.filter(recipe=recipe):
        if product_quantity_map.get(ingredient.product.id, 0) < ingredient.quantity:
            messages.error(request, "Не разполагате с достатъчни продукти за тази рецепта.")
            return redirect("recipe_list")

    # Deduct ingredients from inventory
    for ingredient in RecipeIngredient.objects.filter(recipe=recipe):
        inventory_product = user_inventory.get(product=ingredient.product)
        inventory_product.quantity -= ingredient.quantity
        inventory_product.amount -= ingredient.quantity * inventory_product.average_price
        inventory_product.calculate_average_price()
        inventory_product.save()

    messages.success(request, f"Успешно приготвихте {recipe.name}!")
    return redirect("recipe_list")


@login_required
def generate_recipe_shopping_list(request, recipe_id):
    recipe = Recipe.objects.get(id=recipe_id)
    user_inventory = InventoryProduct.objects.filter(user=request.user)
    product_quantity_map = {item.product.id: item.quantity for item in user_inventory}

    # ✅ Fetch ingredients correctly
    ingredients = RecipeIngredient.objects.filter(recipe=recipe)

    # ✅ Identify missing ingredients
    missing_products = [
        ingredient.product.name
        for ingredient in ingredients  # ✅ Using explicit query
        if product_quantity_map.get(ingredient.product.id, 0) < ingredient.quantity
    ]

    if missing_products:
        # ✅ Create a new shopping list entry
        RecipeShoppingList.objects.create(user=request.user, recipe_name=recipe.name, items=missing_products)
        messages.success(request, f"Списъкът с липсващи продукти за {recipe.name} е успешно генериран!")
    else:
        messages.info(request, f"Всички продукти за {recipe.name} са налични, няма нужда от пазаруване.")

    return redirect("recipe_list")

@login_required
def recipe_view(request, recipe_id):
    recipe = get_object_or_404(Recipe, id=recipe_id)
    user_inventory = InventoryProduct.objects.filter(user=request.user)
    product_price_map = {item.product.id: item.average_price for item in user_inventory}
    product_quantity_map = {item.product.id: item.quantity for item in user_inventory}

    recipe.user_cost = round(sum(product_price_map.get(ingredient.product.id, 0) * ingredient.quantity
                                     for ingredient in recipe.recipe_ingredients.all()), 2)
    recipe.user_availability = all(product_quantity_map.get(ingredient.product.id, 0) >= ingredient.quantity
                                       for ingredient in recipe.recipe_ingredients.all())
    recipe.ingredients_list = RecipeIngredient.objects.filter(recipe=recipe)
    context = {
        "recipe": recipe, 'user_inventory': {item.product.id: item.quantity for item in user_inventory}
    }
    return render(request, "cooking/recipe_view.html", context)


