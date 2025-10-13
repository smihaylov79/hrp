from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.db.models import Count
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from cooking.models import Recipe, RecipeCategory, RecipeIngredient, HouseholdRecipeTimesCooked, RecipeTimesCooked
from inventory.models import InventoryProduct, HouseholdInventoryProduct
from shopping.forms import CreateProductForm
from shopping.models import Product, ProductCategory, HouseholdRecipeShoppingList, RecipeShoppingList


# Create your views here.

def recipe_list(request):
    category_name = request.GET.get('category', 'all')
    recipes = Recipe.objects.all().order_by('category__name')
    categories = RecipeCategory.objects.annotate(recipe_count=Count('recipes'))
    total_recipes = recipes.count()

    all_products = Product.objects.filter(suitable_for_cooking=True).order_by('name')

    ingredient = request.GET.get('ingredient', 'all')

    selected_product = None

    if ingredient != 'all':
        recipes = recipes.filter(ingredients__id=ingredient)
        selected_product = Product.objects.filter(id=ingredient).first()

    user = None
    household = None

    times_cooked = 0
    if request.user.is_authenticated:
        user = request.user
        household = getattr(user, 'household', None)
    else:
        household = None

    if category_name != 'all':
        recipes = recipes.filter(category__name=category_name)

    if household is not None:
        user_inventory = HouseholdInventoryProduct.objects.filter(household=household)

    else:
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
        if household is not None:
            recipe.times_cooked = HouseholdRecipeTimesCooked.objects.filter(household=household, recipe=recipe).count()
        else:
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
               'products': all_products,
               'ingredient': ingredient,
               'total_recipes': total_recipes,
               'product': selected_product,
               }
    return render(request, 'cooking/recipe_list.html', context)


@login_required
def create_recipe(request):
    products = Product.objects.filter(suitable_for_cooking=True).order_by('name')
    categories = RecipeCategory.objects.all()
    product_categories = ProductCategory.objects.all()
    create_product_form = CreateProductForm()

    context = {
        "products": products,
        "categories": categories,
        'product_categories': product_categories,
        'create_product_form': create_product_form,
    }

    return render(request, "cooking/create_recipe.html", context)


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
    user = request.user
    household = user.household
    recipe = Recipe.objects.get(id=recipe_id)
    if household:
        user_inventory = HouseholdInventoryProduct.objects.filter(household=household)
    else:
        user_inventory = InventoryProduct.objects.filter(user=user)
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
    if household:
        HouseholdRecipeTimesCooked.objects.create(household=household, recipe=recipe)
    else:
        RecipeTimesCooked.objects.create(user=request.user, recipe=recipe)

    return redirect("recipe_list")


@login_required
def generate_recipe_shopping_list(request, recipe_id):
    user = request.user
    household = user.household
    recipe = Recipe.objects.get(id=recipe_id)
    if household:
        user_inventory = HouseholdInventoryProduct.objects.filter(household=household)
    else:
        user_inventory = InventoryProduct.objects.filter(user=user)
    product_quantity_map = {item.product.id: item.quantity for item in user_inventory}

    ingredients = RecipeIngredient.objects.filter(recipe=recipe)

    missing_products = [
        ingredient.product.name
        for ingredient in ingredients
        if product_quantity_map.get(ingredient.product.id, 0) < ingredient.quantity
    ]

    if missing_products:
        if household:
            HouseholdRecipeShoppingList.objects.create(household=household, recipe_name=recipe.name, items=missing_products)
        else:
            RecipeShoppingList.objects.create(user=user, recipe_name=recipe.name, items=missing_products)
        messages.success(request, f"Списъкът с липсващи продукти за {recipe.name} е успешно генериран!")
    else:
        messages.info(request, f"Всички продукти за {recipe.name} са налични, няма нужда от пазаруване.")

    return redirect("recipe_list")


def recipe_view(request, recipe_id):
    user = None
    household = None
    times_cooked = 0
    last_cooked = ''
    if request.user.is_authenticated:
        user = request.user
        household = user.household
        recipe = Recipe.objects.get(id=recipe_id)
        if household:
            cooking_history = HouseholdRecipeTimesCooked.objects.filter(household=household, recipe=recipe).order_by('date')
        else:
            cooking_history = RecipeTimesCooked.objects.filter(user=user, recipe=recipe).order_by('date')
        if cooking_history:
            times_cooked = cooking_history.count()
            last_cooked = cooking_history.last().date

    recipe = get_object_or_404(Recipe, id=recipe_id)
    if household and household is not None:
        user_inventory = HouseholdInventoryProduct.objects.filter(household=household)
    else:
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


@login_required
def cooking_home(request):
    user = request.user
    household = getattr(user, 'household', None)
    recent_threshold = timezone.now() - timedelta(days=14)

    # Get recent recipe IDs
    if household:
        recent_cooked_ids = HouseholdRecipeTimesCooked.objects.filter(
            household=household, date__gte=recent_threshold
        ).values_list('recipe_id', flat=True)
        user_inventory = HouseholdInventoryProduct.objects.filter(household=household)
    else:
        recent_cooked_ids = RecipeTimesCooked.objects.filter(
            user=user, date__gte=recent_threshold
        ).values_list('recipe_id', flat=True)
        user_inventory = InventoryProduct.objects.filter(user=user)

    product_quantity_map = {item.product.id: item.quantity for item in user_inventory}

    ready_by_category = defaultdict(list)
    almost_ready = []

    for recipe in Recipe.objects.exclude(id__in=recent_cooked_ids).prefetch_related('recipe_ingredients__product'):
        missing_count = 0
        for ri in recipe.recipe_ingredients.all():
            if product_quantity_map.get(ri.product.id, 0) < ri.quantity:
                missing_count += 1

        if missing_count == 0:
            if len(ready_by_category[recipe.category.name]) < 4:
                ready_by_category[recipe.category.name].append(recipe)
        elif 1 <= missing_count <= 3:
            if len(almost_ready) < 3:
                almost_ready.append((recipe, missing_count))

    return render(request, "cooking/cooking_home.html", {
        "ready_by_category": dict(ready_by_category),
        "almost_ready": almost_ready
    })
