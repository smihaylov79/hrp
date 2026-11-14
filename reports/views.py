from calendar import monthrange

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from django.views.generic import RedirectView, TemplateView

from inventory.models import HouseholdInventoryProduct, InventoryProduct

from . import services
from .filters import ReportFilters
from .models import (HouseholdInflationBasket, HouseholdInflationBasketItem, UserInflationBasket,
                     UserInflationBasketItem)

# (url name, label, icon) - the tabs of the hub, in display order
TABS = [
    ('reports_home', _('Обзор'), 'bi-speedometer2'),
    ('reports_categories', _('Категории'), 'bi-diagram-3'),
    ('reports_shops', _('Магазини'), 'bi-shop'),
    ('reports_prices', _('Цени и инфлация'), 'bi-graph-up-arrow'),
    ('reports_cash_flow', _('Паричен поток'), 'bi-cash-stack'),
    ('reports_budget', _('Бюджет'), 'bi-piggy-bank'),
]


def _int(value):
    return int(value) if value and str(value).isdigit() else None


class ReportTabView(LoginRequiredMixin, TemplateView):
    """One tab of the Reports hub. Subclasses set the tab, its default period and build ``data``."""
    tab = None
    default_period = 'this_month'

    def build(self, filters):
        raise NotImplementedError

    def get(self, request, *args, **kwargs):
        self.filters = ReportFilters(request.GET, default_period=self.default_period)
        self.data = self.build(self.filters)

        export = request.GET.get('export')
        if export:
            table = self.data.get('tables', {}).get(export)
            if table is None:
                raise Http404('Unknown table')
            return table.response(request.GET.get('format', 'csv'))
        return super().get(request, *args, **kwargs)

    def extra_params(self):
        """Tab-specific parameters (drill-down, selected product ...) that filter and export links must keep."""
        return {}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = self.filters
        carried = filters.carry()
        extra = {key: value for key, value in self.extra_params().items() if value not in (None, '', [])}
        context.update({
            'filters': filters,
            'data': self.data,
            'rate_warnings': self.data.get('warnings', []),
            'tabs': [{'label': label, 'icon': icon, 'active': name == self.tab, 'url': reverse(name) + carried}
                     for name, label, icon in TABS],
            'tab_url': reverse(self.tab),
            'preset_links': [dict(link, query=filters.query(period=link['key'], **extra) or f"?period={link['key']}")
                             for link in filters.preset_links()],
            'export_query': filters.query(**extra),
            'hidden_params': [(key, item) for key, value in extra.items()
                              for item in (value if isinstance(value, list) else [value])],
            'show_filters': True,
        })
        return context


class OverviewView(ReportTabView):
    tab = 'reports_home'
    template_name = 'reports/overview.html'

    def build(self, filters):
        return services.overview(self.request.user, filters)


class CategoriesView(ReportTabView):
    tab = 'reports_categories'
    template_name = 'reports/categories.html'

    def build(self, filters):
        self.main_id, self.sub_id = _int(self.request.GET.get('main')), _int(self.request.GET.get('sub'))
        if not self.main_id:
            self.sub_id = None
        return services.categories(self.request.user, filters, self.main_id, self.sub_id)

    def extra_params(self):
        return {'main': self.main_id, 'sub': self.sub_id}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['all_query'] = self.filters.query() or '?'
        context['main_query'] = self.filters.query(main=self.main_id)
        return context


class ShopsView(ReportTabView):
    tab = 'reports_shops'
    template_name = 'reports/shops.html'
    default_period = '3m'

    def build(self, filters):
        self.shop_ids = [int(value) for value in self.request.GET.getlist('shop') if value.isdigit()]
        return services.shops(self.request.user, filters, self.shop_ids)

    def extra_params(self):
        return {'shop': self.shop_ids}


class PricesView(ReportTabView):
    tab = 'reports_prices'
    template_name = 'reports/prices.html'
    default_period = '12m'

    def build(self, filters):
        self.product_id = _int(self.request.GET.get('product'))
        return services.prices(self.request.user, filters, self.product_id)

    def extra_params(self):
        return {'product': self.product_id}


class CashFlowView(ReportTabView):
    tab = 'reports_cash_flow'
    template_name = 'reports/cash_flow.html'
    default_period = '12m'

    def build(self, filters):
        return services.cash_flow(self.request.user, filters)


class BudgetView(ReportTabView):
    tab = 'reports_budget'
    template_name = 'reports/budget.html'
    default_period = 'ytd'

    def build(self, filters):
        return services.budget(self.request.user, filters)


class LegacyReportRedirect(LoginRequiredMixin, RedirectView):
    """Old report addresses (bookmarks, links in old tasks) lead to the matching tab of the hub."""
    target = 'reports_home'
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        old = self.request.GET
        params = {}
        if old.get('date_from') and old.get('date_to'):
            params.update({'period': 'custom', 'from': old['date_from'], 'to': old['date_to']})
        elif old.get('month'):                       # by_category_table?month=2026-10
            try:
                year, month = map(int, old['month'].split('-'))
                params.update({'period': 'custom', 'from': f'{year:04d}-{month:02d}-01',
                               'to': f'{year:04d}-{month:02d}-{monthrange(year, month)[1]:02d}'})
            except (ValueError, TypeError):
                pass
        if old.get('currency'):
            params['currency'] = old['currency']
        if old.get('not_for_household_filter') in ('household', 'external'):
            params['scope'] = old['not_for_household_filter']
        filters = ReportFilters(params)
        extra = {}
        if _int(old.get('product')):
            extra['product'] = _int(old.get('product'))
        if _int(old.get('main_category')):
            extra['main'] = _int(old.get('main_category'))
        return reverse(self.target) + filters.query(**extra)


# ------------------------------------------------------------------------------------------------
# inflation baskets (owned by the household, or by the user when they have no household)
# ------------------------------------------------------------------------------------------------
def user_inflation_baskets(user):
    """Inflation baskets owned by the user's household, or by the user when they have no household."""
    if user.household:
        return HouseholdInflationBasket.objects.filter(household=user.household)
    return UserInflationBasket.objects.filter(user=user)


def user_inventory_products(user):
    """Inventory rows that may be put in a basket: only the owner's."""
    if user.household:
        return HouseholdInventoryProduct.objects.filter(household=user.household)
    return InventoryProduct.objects.filter(user=user)


def _basket_page_context(request, **extra):
    """Context of the basket forms: they live under the "Prices" tab but have no filter bar."""
    context = {
        'filters': ReportFilters({}, default_period='12m'),
        'tabs': [{'label': label, 'icon': icon, 'active': name == 'reports_prices', 'url': reverse(name)}
                 for name, label, icon in TABS],
        'show_filters': False,
        'products': user_inventory_products(request.user).select_related('product').order_by('product__name'),
    }
    context.update(extra)
    return context


@login_required
def create_inflation_basket(request):
    return render(request, 'reports/create_inflation_basket.html', _basket_page_context(request))


def _basket_name_error(request, name, exclude_pk=None):
    """Validate a basket name for the current owner; returns an error text or None."""
    if not name:
        return _("Името на кошницата е задължително.")
    same_name = user_inflation_baskets(request.user).filter(name=name)
    if exclude_pk:
        same_name = same_name.exclude(pk=exclude_pk)
    if same_name.exists():
        return _("Вече имате кошница с това име.")
    return None


@login_required
@require_POST
def save_inflation_basket(request):
    user = request.user
    household = user.household
    name = request.POST.get('name', '').strip()
    error = _basket_name_error(request, name)
    if error:
        messages.error(request, error)
        return redirect('create_inflation_basket')

    # only the owner's inventory rows may go in the basket
    product_ids = [pk for pk in request.POST.getlist("product_id[]") if pk.isdigit()]
    products = user_inventory_products(user).filter(id__in=product_ids)
    if household:
        basket = HouseholdInflationBasket.objects.create(household=household, name=name)
        HouseholdInflationBasketItem.objects.bulk_create(
            [HouseholdInflationBasketItem(basket=basket, product=product) for product in products])
    else:
        basket = UserInflationBasket.objects.create(user=user, name=name)
        UserInflationBasketItem.objects.bulk_create(
            [UserInflationBasketItem(basket=basket, product=product) for product in products])
    messages.success(request, _("Кошницата е създадена."))
    return redirect('reports_prices')


@login_required
def edit_inflation_basket(request, basket_id):
    user = request.user
    household = user.household
    basket = get_object_or_404(user_inflation_baskets(user), id=basket_id)
    products = user_inventory_products(user)
    if household:
        item_model, items = HouseholdInflationBasketItem, basket.household_basket_items
    else:
        item_model, items = UserInflationBasketItem, basket.user_basket_items
    selected_ids = items.values_list("product_id", flat=True)

    if request.method == "POST":
        name = request.POST.get('name', '').strip()
        error = _basket_name_error(request, name, exclude_pk=basket.pk)
        if error:
            messages.error(request, error)
            return redirect('edit_inflation_basket', basket_id=basket.pk)
        basket.name = name
        basket.save()
        new_ids = [pk for pk in request.POST.getlist("product_id[]") if pk.isdigit()]
        new_products = list(products.filter(id__in=new_ids))
        # replaces the basket's own item rows (same behaviour as before, now limited to the owner's products)
        items.all().delete()
        item_model.objects.bulk_create([item_model(basket=basket, product=product) for product in new_products])
        messages.success(request, _("Кошницата е записана."))
        return redirect('reports_prices')

    return render(request, 'reports/edit_inflation_basket.html',
                  _basket_page_context(request, basket=basket, selected_ids=list(selected_ids)))
