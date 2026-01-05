from collections import defaultdict
from datetime import date

import pandas as pd
from django.db.models import Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
import json

from income.models import Income, IncomeType
from reports.utils import db_to_df, income_db_to_df
from .models import Budget, BudgetItem, BudgetApproval, BudgetIncomeItem
from .forms import BudgetForm, BudgetItemForm, BudgetApprovalForm
from shopping.models import ShoppingProduct, MainCategory
from users.models import CustomUser

from decimal import Decimal



@login_required
def budget_home(request):
    """Начална страница за budgeting app"""
    user = request.user
    household = getattr(user, "household", None)

    # показваме всички бюджети, които са релевантни за потребителя
    if household:
        budgets = Budget.objects.filter(household=household)
    else:
        budgets = Budget.objects.filter(creator=user, household__isnull=True)

    for budget in budgets:
        budget.planned_year = budget.date_to.year
        budget.amount = BudgetItem.objects.filter(budget=budget).aggregate(Sum('planned_amount'))['planned_amount__sum']
        budget.can_be_tracked = True
        if date.today() < budget.date_from:
            budget.can_be_tracked = False

    return render(request, "budget/budget_home.html", {"budgets": budgets})





@login_required
def propose_budget(request):
    user = request.user
    household = getattr(user, "household", None)

    # финализиране на бюджета
    if request.method == "POST" and request.POST.get("action") == "finalize":
        budget_id = request.POST.get("budget_id")
        budget = Budget.objects.get(pk=budget_id)
        budget.items.all().delete()
        budget.income_items.all().delete()

        cat_values = defaultdict(list)
        for key, val in request.POST.items():
            if key.startswith("month_"):
                try:
                    _, cat, _ = key.split("_", 2)
                    amt = Decimal(val or "0").quantize(Decimal("1"))
                    cat_values[cat].append(amt)
                except Exception:
                    continue

        for cat, vals in cat_values.items():
            category = MainCategory.objects.filter(name=cat).first()
            if category:
                total = sum(vals).quantize(Decimal("1"))
                BudgetItem.objects.create(budget=budget, category=category, planned_amount=total)

        income_values = defaultdict(list)
        for key, val in request.POST.items():
            if key.startswith("income_"):
                try:
                    _, cat, _ = key.split("_", 2)
                    amt = Decimal(val or "0").quantize(Decimal("1"))
                    income_values[cat].append(amt)
                except Exception:
                    continue

        for cat, vals in income_values.items():
            income_type = IncomeType.objects.filter(name=cat).first()
            if income_type:
                total = sum(vals).quantize(Decimal("1"))
                BudgetIncomeItem.objects.create(
                    budget=budget,
                    income_type=income_type,
                    planned_amount=total
                )

        budget.submitted = True
        budget.approved = False if household else True
        budget.save()

        if household:
            members = household.household.all()
            for member in members:
                BudgetApproval.objects.get_or_create(budget=budget, user=member)

        return redirect("budget_detail", pk=budget.pk)

    # генериране на предложение
    form = BudgetForm(request.POST or None)
    if request.method == "POST" and form.is_valid() and request.POST.get("action") == "generate":
        budget = form.save(commit=False)
        budget.creator = user
        budget.household = household if household else None
        budget.submitted = False
        budget.approved = False
        budget.save()

        # взимаме историята
        if household:
            members = CustomUser.objects.filter(household=household)
            shopping_qs = ShoppingProduct.objects.filter(shopping__user__in=members)
        else:
            shopping_qs = ShoppingProduct.objects.filter(shopping__user=user)

        df = db_to_df(shopping_qs, budget.currency)

        df["month"] = pd.to_datetime(df["shopping__date"]).dt.month

        # същата логика като в SpendingsView
        main_category_monthly = (
            df.groupby(['month', 'product__category__main_category__name'])['total']
            .sum()
            .reset_index()
        )

        month_labels = sorted(main_category_monthly['month'].unique())
        main_categories = main_category_monthly['product__category__main_category__name'].unique()

        planned_year = budget.date_to.year # напр. 2026
        planned_months = [f"{planned_year}-{str(m).zfill(2)}" for m in range(1, 13)]

        # подготвяме редове за таблицата
        proposal_rows = []
        for category in main_categories:

            # взимаме всички стойности за категорията
            cat_data = main_category_monthly[
                main_category_monthly['product__category__main_category__name'] == category
                ]

            # средна стойност за категорията
            avg_val = int(round(cat_data['total'].mean(), 0)) if not cat_data.empty else 0

            row = {"category": category, "months": [], "total": 0}
            for m in range(1, 13):
                # проверяваме дали има стойност за този месец в историята
                value = cat_data[cat_data['month'] == m]['total']
                val = int(round(value.values[0], 0)) if not value.empty else avg_val
                row["months"].append(val)
            row["total"] = sum(row["months"])
            proposal_rows.append(row)


        # for the incomes
        if household:
            members = CustomUser.objects.filter(household=household)
            income_qs = Income.objects.filter(user__in=members)
        else:
            income_qs = Income.objects.filter(user=user)

        df_income = income_db_to_df(income_qs, budget.currency)  # същата функция, но работи и за приходи

        income_monthly = (
            df_income.groupby(['month', 'income_type__name'])['total']
            .sum()
            .reset_index()
        )
        income_monthly['category'] = income_monthly['income_type__name']

        planned_year = budget.date_to.year
        income_months = [f"{planned_year}-{str(m).zfill(2)}" for m in range(1, 13)]

        income_rows = []
        for category in income_monthly['category'].unique():
            cat_data = income_monthly[income_monthly['category'] == category]
            avg_val = int(round(cat_data['total'].mean(), 0)) if not cat_data.empty else 0

            row = {'category': category, "months": [], "total": 0}
            for m in range(1, 13):
                value = cat_data[cat_data['month'] == m]['total']
                val = int(round(value.values[0], 0)) if not value.empty else avg_val
                row["months"].append(val)
            row["total"] = sum(row["months"])
            income_rows.append(row)

        context = {
            "form": form,
            "budget": budget,
            "proposal_rows": proposal_rows,
            "month_columns": planned_months,
            "currency": budget.currency,
            "income_rows": income_rows,
            "income_months": income_months,
        }
        return render(request, "budget/propose_edit.html", context)
    return render(request, "budget/propose.html", {"form": BudgetForm()})



@login_required
def budget_detail(request, pk):
    budget = get_object_or_404(Budget, pk=pk)
    approvals = BudgetApproval.objects.filter(budget=budget)

    user_approval = approvals.filter(user=request.user).first()

    total_amount = BudgetItem.objects.filter(budget=budget).aggregate(Sum('planned_amount'))['planned_amount__sum']
    total_income = BudgetIncomeItem.objects.filter(budget=budget).aggregate(Sum('planned_amount'))['planned_amount__sum']

    if request.method == "POST" and request.POST.get("action") == "approve":
        approval = BudgetApproval.objects.filter(budget=budget, user=request.user).first()
        if approval:
            approval.approved = True
            approval.approved_at = timezone.now()
            approval.save()

        if budget.check_all_approved():
            budget.approved = True
            budget.save(update_fields=["approved"])
        return redirect("budget_detail", pk=budget.pk)

    if budget.check_all_approved() and not budget.approved:
        budget.approved = True
        budget.save(update_fields=["approved"])

    context = {
        "budget": budget,
        "approvals": approvals,
        "user_approval": user_approval,
        "total_amount": total_amount,
        "total_income": total_income,
    }
    return render(request, "budget/detail.html", context)


@login_required
def track_budget(request, pk):
    """Track изпълнението спрямо реалните разходи"""
    budget = get_object_or_404(Budget, pk=pk)
    items = budget.items.all()
    income_items = BudgetIncomeItem.objects.filter(budget=budget)
    today = date.today()
    total_days = (budget.date_to - budget.date_from).days + 1
    # days_passed = max(0, min((today - budget.date_from).days + 1, total_days))
    days_passed = (today - budget.date_from).days + 1

    time_percent = round(days_passed / total_days * 100, 2)

    # реални разходи по категории
    users_scope = budget.scope_users()
    spendings_qs = ShoppingProduct.objects.filter(shopping__user__in=users_scope,
                                                  shopping__date__range=(budget.date_from, budget.date_to))
    df = db_to_df(spendings_qs, budget.currency)
    actual_by_category = df.groupby("product__category__main_category__name")["total"].sum().to_dict()

    income_qs = Income.objects.filter(user__in=users_scope, date_received__range=(budget.date_from, budget.date_to))
    income_df = income_db_to_df(income_qs, budget.currency)
    actual_income = income_df['total'].sum()
    planned_income = float(income_items.aggregate(Sum('planned_amount'))['planned_amount__sum'])

    tracking = []
    for item in items:
        planned = item.planned_amount
        actual = actual_by_category.get(item.category.name, 0)
        ytd_planned = (planned  / total_days) * days_passed
        percent_ytd = 0
        if planned > 0:
            percent_ytd = round((float(actual) / float(ytd_planned) * 100), 2)
        tracking.append({
            "category": item.category.name,
            "planned": round(float(item.planned_amount),2),
            "actual": round(float(actual),2),
            "ytd": round(ytd_planned, 2),
            "percent": round((float(actual) / float(item.planned_amount) * 100) if item.planned_amount else 0, 2),
            "percent_ytd": percent_ytd,
        })

    categories = [row["category"] for row in tracking]
    planned_series = [row["planned"] for row in tracking]
    actual_series = [row["actual"] for row in tracking]

    total_planned = sum(row["planned"] for row in tracking)
    total_actual = sum(row["actual"] for row in tracking)
    total_percent = round((total_actual / total_planned * 100) if total_planned else 0, 2)

    time_is_behind = time_percent < total_percent

    ytd_total_planned = (total_planned / total_days) * days_passed
    ytd_planned_income = (planned_income / total_days) * days_passed
    income_percent = actual_income / planned_income * 100 if planned_income else 0
    income_issue = actual_income < total_actual

    context = {
        "budget": budget,
        "tracking": tracking,
        "categories": json.dumps(categories),
        "planned_series": json.dumps(planned_series),
        "actual_series": json.dumps(actual_series),
        "total_planned": total_planned,
        "total_actual": round(total_actual, 2),
        "total_percent": total_percent,
        "time_percent": time_percent,
        "ytd_planned": round(ytd_total_planned, 2),
        "time_is_behind": time_is_behind,
        "ytd_planned_income": round(ytd_planned_income, 2),
        "income_percent": round(income_percent, 2),
        "planned_income": planned_income,
        "actual_income": round(actual_income, 2),
        "income_issue": income_issue,
    }

    return render(request, "budget/track.html", context)


@login_required
def edit_budget(request, pk):
    budget = get_object_or_404(Budget, pk=pk)
    items = budget.items.select_related("category").all()
    income_items = budget.income_items.select_related("income_type").all()

    if request.method == "POST":
        # Update each item
        for item in items:
            field_name = f"item_{item.id}"
            value = request.POST.get(field_name, "0")
            item.planned_amount = Decimal(value)
            item.save()

        for item in income_items:
            field_name = f"item_{item.id}"
            value = request.POST.get(field_name, "0")
            item.planned_amount = Decimal(value)
            item.save()

        # Reset approvals
        budget.reset_approvals()

        return redirect("budget_detail", pk=budget.pk)

    return render(request, "budget/edit.html", {
        "budget": budget,
        "items": items,
        "income_items": income_items,
        "currency": budget.currency,
    })
