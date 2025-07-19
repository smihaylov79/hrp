from decimal import Decimal

from inventory.models import HouseholdInventoryProduct, HouseholdProductCategory, InventoryProduct, UserProductCategory
from shopping.models import HouseholdShoppingList, ShoppingList, Product, ShoppingProduct, Shopping


def load_prefill_data(request, user, household):
    selected_list_id = request.GET.get("list")
    prefill_data = []

    if not selected_list_id:
        return prefill_data

    else:
        try:
            if household:
                shopping_list = HouseholdShoppingList.objects.get(id=selected_list_id, household=household)
            else:
                shopping_list = ShoppingList.objects.get(id=selected_list_id, user=user)
            for item_name in shopping_list.items:
                product = Product.objects.filter(name=item_name).first()
                if product:
                    last_price = 0.00
                    shoppings = Shopping.objects.filter(user=user)
                    shoppings_ids = [sh.id for sh in shoppings]
                    shopping_product = ShoppingProduct.objects.filter(product=product.id,
                                                                      shopping__in=shoppings_ids).order_by('id').last()
                    if shopping_product:
                        last_price = shopping_product.price
                    prefill_data.append({
                        "product_id": product.id,
                        "name": product.name,
                        "quantity": 1,
                        "price": last_price,
                        "discount": 0,
                        "not_for_household": False,
                    })
        except ShoppingList.DoesNotExist:
            pass
        return prefill_data


def save_shopping_products(selected_products, shopping, user, household):
    for product_data in selected_products:
        product = Product.objects.get(id=product_data["product_id"])
        quantity = Decimal(product_data["quantity"])
        price = Decimal(product_data["price"])
        discount = Decimal(product_data["discount"] if product_data["discount"] else 0)
        amount = quantity * price - discount

        not_for_household = product_data['not_for_household']

        ShoppingProduct.objects.create(
            shopping=shopping, product=product, quantity=quantity, price=price,
            discount=discount, amount=amount, not_for_household=not_for_household
        )
        if household:
            inventory_product, created = HouseholdInventoryProduct.objects.get_or_create(
                household=household, product=product, category=product.category,
                defaults={"quantity": 0, "amount": 0, "inventory_related": True}
            )
            if inventory_product.inventory_related and not not_for_household:
                inventory_product.quantity += quantity
                inventory_product.amount += amount
                inventory_product.calculate_average_price()
                inventory_product.save()

            household_product_category, created = HouseholdProductCategory.objects.get_or_create(household=household,
                                                                                                 product_category=product.category)
            household_product_category.save()

        else:
            inventory_product, created = InventoryProduct.objects.get_or_create(
                user=user, product=product, category=product.category,
                defaults={"quantity": 0, "amount": 0, "inventory_related": True}
            )
            if inventory_product.inventory_related and not not_for_household:
                inventory_product.quantity += quantity
                inventory_product.amount += amount
                inventory_product.calculate_average_price()
                inventory_product.save()

            user_product_category, created = UserProductCategory.objects.get_or_create(user=user,
                                                                                       product_category=product.category)
            user_product_category.save()