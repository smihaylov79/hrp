from decimal import Decimal
from django.shortcuts import render
from .forms import ChangeCalculatorForm
from .services import convert  # your DB-based convert()

def change_calculator_view(request):
    result = None

    if request.method == "POST":
        form = ChangeCalculatorForm(request.POST)

        if form.is_valid():
            paid_amount = form.cleaned_data["paid_amount"]
            paid_currency = form.cleaned_data["paid_currency"]
            bill_amount = form.cleaned_data["bill_amount"]
            bill_currency = form.cleaned_data["bill_currency"]

            # Convert paid amount to BGN
            if paid_currency == "BGN":
                paid_bgn = Decimal(paid_amount)
            else:
                paid_bgn = convert(paid_amount, paid_currency, "BGN")

            # Convert bill amount to BGN
            if bill_currency == "BGN":
                bill_bgn = Decimal(bill_amount)
            else:
                bill_bgn = convert(bill_amount, bill_currency, "BGN")

            # Calculate change
            change_bgn = paid_bgn - bill_bgn

            # Convert BGN → EUR using fixed rate
            change_eur = change_bgn / Decimal("1.95583")

            result = {
                "change_bgn": round(change_bgn, 2),
                "change_eur": round(change_eur, 2),
            }

    else:
        form = ChangeCalculatorForm()

    return render(
        request,
        "change_calculator/index.html",
        {"form": form, "result": result},
    )

