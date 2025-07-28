from inventory.models import InventoryProduct, HouseholdInventoryProduct, UserProductCategory, HouseholdProductCategory


def merge_user_inventory_to_household(user, household):
    user_inventory = InventoryProduct.objects.filter(user=user)
    user_categories = UserProductCategory.objects.filter(user=user)

    for item in user_inventory:
        household_item, created = HouseholdInventoryProduct.objects.get_or_create(
            household=household,
            product=item.product,
            defaults={
                "category": item.category,
                "quantity": item.quantity,
                "amount": item.amount,
                "average_price": item.average_price,
                "daily_consumption": item.daily_consumption,
                "minimum_quantity": item.minimum_quantity,
                "inventory_related": item.inventory_related
            }
        )

        if not created:
            household_item.quantity += item.quantity
            household_item.amount += item.amount
            household_item.daily_consumption = max(household_item.daily_consumption, item.daily_consumption)
            household_item.minimum_quantity = max(household_item.minimum_quantity, item.minimum_quantity)

            household_item.calculate_average_price()
            household_item.save()

    for item in user_categories:
        HouseholdProductCategory.objects.get_or_create(
            household=household,
            product_category=item.product_category,
            direct_planning=item.direct_planning,
            daily_consumption = item.daily_consumption,
            minimum_quantity=item.minimum_quantity,
        )
