"""Data for the home dashboard. Everything is scoped to the user (or their household) and kept query-light."""
import calendar
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import F, Prefetch, Q
from django.utils import timezone

from budget.models import Budget, BudgetItem
from cooking.models import HouseholdRecipeTimesCooked, RecipeTimesCooked
from cooking.services import inventory_maps, missing_ingredients, recipe_catalogue, recipe_cost, user_inventory_queryset
from reports.currency import DEFAULT_CURRENCY
from reports.utils import db_to_df, rate_warnings
from shopping.models import ShoppingProduct
from taskmanager.models import Event, Task
from users.models import CustomUser

BUDGET_ROWS = 4
LIST_ROWS = 4


def _user_purchases(user):
    if user.household_id:
        return ShoppingProduct.objects.filter(shopping__user__household_id=user.household_id)
    return ShoppingProduct.objects.filter(shopping__user=user)


def tasks_and_events(user, today):
    """Open tasks due today or earlier (overdue first) and today's remaining events."""
    open_tasks = list(Task.objects.filter(user=user, completed=False, due_date__lte=today).order_by('due_date', 'id'))
    now = timezone.now()
    end_of_day = timezone.make_aware(datetime.combine(today, time.max))
    start_of_day = timezone.make_aware(datetime.combine(today, time.min))
    events = list(Event.objects.filter(user=user, start_datetime__lte=end_of_day)
                  .filter(Q(end_datetime__gte=now) | Q(start_datetime__gte=start_of_day)).order_by('start_datetime')[:LIST_ROWS])
    overdue = [task for task in open_tasks if task.due_date < today]
    return {
        'tasks_today': len(open_tasks) - len(overdue),
        'tasks_overdue': len(overdue),
        'task_total': len(open_tasks),
        'task_rows': [{'task': task, 'overdue': task.due_date < today} for task in open_tasks[:LIST_ROWS]],
        'events_today': events,
    }


def month_spending(user, today):
    """Spending from the 1st of the month until today, in the default currency, total and per main category."""
    start = today.replace(day=1)
    df = db_to_df(_user_purchases(user).filter(shopping__date__range=(start, today)), DEFAULT_CURRENCY)
    total = float(df['total'].sum()) if not df.empty else 0.0
    by_category = (df.groupby('product__category__main_category__name')['total'].sum().to_dict() if not df.empty else {})
    return {
        'month_total': round(total, 2),
        'month_per_day': round(total / today.day, 2),
        'month_days': today.day,
        'month_by_category': by_category,
        'rate_warnings': rate_warnings(df),
        'currency': DEFAULT_CURRENCY,
    }


def budget_progress(user, today, spent_by_category):
    """This month's share of the current budget against month-to-date spending.

    A budget covers a longer period (usually a year); the monthly plan of a category is its planned amount
    spread evenly over the budget's days. Returns None when no approved/submitted budget covers today or when
    the budget is in another currency than the dashboard (amounts would not be comparable).
    """
    if user.household_id:
        budgets = Budget.objects.filter(household_id=user.household_id)
    else:
        budgets = Budget.objects.filter(creator=user, household__isnull=True)
    budget = (budgets.filter(submitted=True, date_from__lte=today, date_to__gte=today)
              .prefetch_related(Prefetch('items', queryset=BudgetItem.objects.select_related('category')))
              .order_by('-date_from').first())
    if budget is None or budget.currency != DEFAULT_CURRENCY:
        return None

    budget_days = (budget.date_to - budget.date_from).days + 1
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    month_share = Decimal(days_in_month) / Decimal(budget_days)
    pace = round(today.day / days_in_month * 100)

    rows, planned_total, spent_total = [], 0.0, 0.0
    for item in budget.items.all():
        planned = float(item.planned_amount * month_share)
        spent = float(spent_by_category.get(item.category.name, 0))
        planned_total += planned
        spent_total += spent
        if planned <= 0:
            continue
        percent = spent / planned * 100
        rows.append({
            'name': item.category.name,
            'planned': round(planned),
            'spent': round(spent),
            'percent': round(percent),
            'width': min(round(percent), 100),
            'state': 'exceeded' if percent > 100 else ('ahead' if percent > pace + 5 else 'ok'),
        })
    rows.sort(key=lambda row: row['planned'], reverse=True)
    percent_total = round(spent_total / planned_total * 100) if planned_total else 0
    return {
        'budget': budget,
        'rows': rows[:BUDGET_ROWS],
        'percent': percent_total,
        'pace': pace,
        'points_over_pace': percent_total - pace,
    }


def ready_recipes(user):
    """Recipes the user can cook now (not cooked in the last 14 days) plus the closest "almost ready" one."""
    prices, quantities = inventory_maps(user)
    if not quantities:
        return []
    recent = timezone.now() - timedelta(days=14)
    if user.household_id:
        cooked = HouseholdRecipeTimesCooked.objects.filter(household_id=user.household_id, date__gte=recent)
    else:
        cooked = RecipeTimesCooked.objects.filter(user=user, date__gte=recent)
    recently_cooked = set(cooked.values_list('recipe_id', flat=True))

    ready, almost = [], []
    for recipe in recipe_catalogue():
        if recipe.id in recently_cooked or not recipe.recipe_ingredients.all():
            continue
        missing = missing_ingredients(recipe, quantities)
        if missing == 0 and len(ready) < LIST_ROWS - 1:
            ready.append({'recipe': recipe, 'missing': 0, 'cost': recipe_cost(recipe, prices)})
        elif missing == 1 and not almost:
            almost.append({'recipe': recipe, 'missing': 1, 'cost': None})
        if len(ready) == LIST_ROWS - 1 and almost:
            break
    return ready + almost


def low_stock(user):
    """Inventory rows below their minimum quantity."""
    return list(user_inventory_queryset(user)
                .filter(inventory_related=True, minimum_quantity__gt=0, quantity__lt=F('minimum_quantity'))
                .select_related('product').order_by('product__name')[:LIST_ROWS])


def household_name(user):
    return user.household.name if user.household_id else None


def build(user):
    """Whole dashboard context for a logged-in user."""
    today = timezone.localdate()
    context = {'today': today, 'household_name': household_name(user)}
    context.update(tasks_and_events(user, today))
    spending = month_spending(user, today)
    context.update(spending)
    context['budget_progress'] = budget_progress(user, today, spending['month_by_category'])
    context['ready_recipes'] = ready_recipes(user)
    context['low_stock'] = low_stock(user)
    return context


def search(user, query, limit=8):
    """Simple global search in the user's own data: bought products, recipes, tasks."""
    from cooking.models import Recipe
    from shopping.models import Product

    query = (query or '').strip()
    if len(query) < 2:
        return {'products': [], 'recipes': [], 'tasks': []}
    if user.household_id:
        members = CustomUser.objects.filter(household_id=user.household_id)
        bought = Product.objects.filter(shoppingproduct__shopping__user__in=members)
    else:
        bought = Product.objects.filter(shoppingproduct__shopping__user=user)
    return {
        'products': list(bought.filter(name__icontains=query).distinct().order_by('name')[:limit]),
        'recipes': list(Recipe.objects.filter(name__icontains=query).select_related('category').order_by('name')[:limit]),
        'tasks': list(Task.objects.filter(user=user, title__icontains=query).order_by('completed', '-due_date')[:limit]),
    }
