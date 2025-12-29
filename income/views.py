from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Income, IncomeType
from .forms import IncomeForm, IncomeTypeForm


@login_required
def income_home(request):
    user = request.user
    if user.household:
        # всички приходи на домакинството
        incomes = Income.objects.filter(user__household=user.household).order_by('-date_received')
    else:
        # само приходите на потребителя
        incomes = Income.objects.filter(user=user).order_by('-date_received')

    return render(request, "income/income_home.html", {"incomes": incomes})


@login_required
def income_type_list(request):
    types = IncomeType.objects.all()
    return render(request, "income/income_type_list.html", {"types": types})


@login_required
def create_income_type(request):
    if request.method == "POST":
        form = IncomeTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Успешно добави нов вид приход!")
            return redirect("income_type_list")
    else:
        form = IncomeTypeForm()
    return render(request, "income/create_income_type.html", {"form": form})


@login_required
def register_income(request):
    if request.method == "POST":
        form = IncomeForm(request.POST)
        if form.is_valid():
            income = form.save(commit=False)
            income.user = request.user
            income.save()
            messages.success(request, "Приходът е успешно регистриран!")
            return redirect("income_home")
    else:
        form = IncomeForm()
    return render(request, "income/register_income.html", {"form": form})
