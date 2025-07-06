from django.db.models import Sum, Count, Max, Min
from django.db.models.functions import TruncMonth, TruncWeek, ExtractWeek
from django.shortcuts import render
from inventory.models import *
from shopping.models import *
import json
from django.views.generic import FormView
from .forms import *
from datetime import date
from .utils import calculate_price_changes


# Create your views here.


class ReportsHomeView(FormView):
    template_name = 'reports/reports_home_main.html'
    form_class = ReportFilterForm

    def get(self, request, *args, **kwargs):
        form = self.form_class(self.request.GET or None)
        context = self.get_context_data(form=form)

        if form.is_valid():
            user = self.request.user
            shopping_data = ShoppingProduct.objects.filter(shopping__user=user)
            main_category = form.cleaned_data.get('main_category')
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')

            if main_category:
                shopping_data = shopping_data.filter(product__category_id__main_category_id=main_category.id)

            if date_from and date_to:
                shopping_data = shopping_data.filter(shopping__date__range=(date_from, date_to))
            elif date_from:
                shopping_data = shopping_data.filter(shopping__date__gte=date_from)
            elif date_to:
                shopping_data = shopping_data.filter(shopping__date__lte=date_to)

            total_spent = shopping_data.aggregate(total=Sum('amount'))['total']
            monthly_spent = shopping_data.annotate(month=TruncMonth('shopping__date')).values('month').annotate(
                total_amount=Sum('amount')).order_by('month')
            weekly_spent = shopping_data.annotate(week=ExtractWeek('shopping__date')).values('week').annotate(
                total_amount=Sum('amount')).order_by('week')

            monthly_data = [
                {'month': entry['month'].strftime('%m.%Y'), 'total': float(entry['total_amount'])} for entry in
                monthly_spent
            ]
            weekly_data = [{'week': entry['week'], 'total': float(entry['total_amount'])} for entry in weekly_spent]


            main_category_spending = shopping_data.values("product__category__main_category__name").annotate(
                total_spent=Sum("amount"))
            subcategory_spending = shopping_data.values("product__category__name").annotate(total_spent=Sum("amount"))

            main_chart_data = [
                {"name": entry["product__category__main_category__name"], "y": float(entry["total_spent"])}
                for entry in main_category_spending]
            sub_chart_data = [{"name": entry["product__category__name"], "y": float(entry["total_spent"])}
                              for entry in subcategory_spending]

            shoppings_count = shopping_data.aggregate(shoppings_count=Count('shopping', distinct=True))['shoppings_count']
            most_purchased = (
                shopping_data.values('product__name').annotate(purchase_count=Count('id')).order_by('-purchase_count')[:5]
            )
            most_purchased_names = ', '.join([entry['product__name'] for entry in most_purchased])
            biggest_spent = shopping_data.values('product__name').annotate(spent=Max('amount')).order_by('-spent').first()
            lowest_price = shopping_data.exclude(price=0).values('product__name').annotate(price=Min('price')).order_by('price').first()
            highest_price = shopping_data.values('product__name').annotate(price=Max('price')).order_by('-price').first()

            price_changes = calculate_price_changes(shopping_data.exclude(price=0).values(
                                            'product__name','price', 'shopping__date').order_by('product__name', 'shopping__date'))
            top_increase = price_changes[0][:1][0] if price_changes[0] else None
            top_decrease = price_changes[1][:1][0] if price_changes[1] else None


            context = self.get_context_data(form=form, )
            context.update({'monthly_data': json.dumps(monthly_data),
                            'weekly_data': json.dumps(weekly_data),
                            'total_spent': total_spent,
                            'main_category_name': main_category.name if main_category else '',
                            'main_chart_data': json.dumps(main_chart_data),
                            'sub_chart_data': json.dumps(sub_chart_data),
                            'most_purchased': most_purchased,
                            'shoppings_count': shoppings_count,
                            'most_purchased_names': most_purchased_names,
                            'biggest_spent': biggest_spent,
                            'lowest_price': lowest_price,
                            'highest_price': highest_price,
                            'top_increase': top_increase,
                            'top_decrease': top_decrease,
                            })
        return self.render_to_response(context)


#
#
#
# def reports_home(request):
#     user=request.user
#     main_categories = MainCategory.objects.all()
#
#     main_category_filter = request.GET.get("main_category", "")
#     main_category_name = ""
#
#     date_from_filter = request.GET.get("date_from", "")
#     date_to_filter = request.GET.get("date_to", '')
#
#     shopping_data = ShoppingProduct.objects.filter(shopping__user=user)
#
#     if main_category_filter and main_category_filter.strip():
#         shopping_data = shopping_data.filter(product__category_id__main_category_id=main_category_filter)
#         main_category = main_categories.filter(id=main_category_filter).first()
#         main_category_name = main_category.name
#
#     if date_from_filter and date_to_filter:
#         shopping_data = shopping_data.filter(shopping__date__range=(date_from_filter, date_to_filter))
#
#     elif date_from_filter:
#         shopping_data = shopping_data.filter(shopping__date__gte=date_from_filter)
#
#     elif date_to_filter:
#         shopping_data = shopping_data.filter(shopping__date__lte=date_to_filter)
#
#     # if date_to_filter:
#     #     shopping_data = shopping_data.filter(shopping__date=date_to_filter)
#
#     total_spent = shopping_data.aggregate(total=Sum('amount'))['total']
#     monthly_spent = shopping_data.annotate(month=TruncMonth('shopping__date')).values('month').annotate(
#         total_amount=Sum('amount')).order_by('month')
#     weekly_spent = shopping_data.annotate(week=ExtractWeek('shopping__date')).values('week').annotate(
#         total_amount=Sum('amount')).order_by('week')
#
#     monthly_data = [
#         {'month': entry['month'].strftime('%m.%Y'), 'total': float(entry['total_amount'])} for entry in monthly_spent
#     ]
#     weekly_data = [{'week': entry['week'], 'total': float(entry['total_amount'])} for entry in weekly_spent]
#
#
#     context = {
#         'total_spent': total_spent,
#         'monthly_data': json.dumps(monthly_data),
#         'weekly_data': json.dumps(weekly_data),
#         'main_categories': main_categories,
#         "main_category_name": main_category_name,
#         'date_from_filter': date_from_filter,
#         'date_to_filter': date_to_filter,
#     }
#
#     return render(request, 'reports/reports_home.html', context)

def spending_history(request, period):
    user = request.user
