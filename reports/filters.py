"""The shared filter bar of the Reports hub: period, currency and scope, all kept in the URL."""
from datetime import date
from urllib.parse import urlencode

from dateutil.relativedelta import relativedelta
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from shopping.models import CurrencyChoice

from .currency import DEFAULT_CURRENCY, normalise_currency

PRESETS = [
    ('this_month', gettext_lazy('Този месец')),
    ('last_month', gettext_lazy('Миналия месец')),
    ('3m', gettext_lazy('3 м')),
    ('6m', gettext_lazy('6 м')),
    ('12m', gettext_lazy('12 м')),
    ('ytd', gettext_lazy('От началото на годината')),
]
SCOPES = [
    ('all', gettext_lazy('Всички разходи')),
    ('household', gettext_lazy('За домакинството')),
    ('external', gettext_lazy('Извън домакинството')),
    ('mine', gettext_lazy('Само моите')),
]
PRESET_KEYS = [key for key, _label in PRESETS]
SCOPE_KEYS = [key for key, _label in SCOPES]


def _parse_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


class ReportFilters:
    """Parsed, always-valid filter values. Unknown or broken input falls back to the defaults."""

    def __init__(self, params, default_period='this_month', today=None):
        self.today = today or timezone.localdate()
        self.default_period = default_period
        self.currency = normalise_currency(params.get('currency'), DEFAULT_CURRENCY)
        scope = params.get('scope')
        self.scope = scope if scope in SCOPE_KEYS else 'all'

        date_from, date_to = _parse_date(params.get('from')), _parse_date(params.get('to'))
        period = params.get('period')
        if period == 'custom' and date_from and date_to and date_from <= date_to:
            self.period, self.start, self.end = 'custom', date_from, date_to
        else:
            self.period = period if period in PRESET_KEYS else default_period
            self.start, self.end = self._preset_range(self.period)

    def _preset_range(self, period):
        today = self.today
        first = today.replace(day=1)
        if period == 'last_month':
            return first - relativedelta(months=1), first - relativedelta(days=1)
        if period in ('3m', '6m', '12m'):
            months = int(period[:-1])
            return today - relativedelta(months=months) + relativedelta(days=1), today
        if period == 'ytd':
            return today.replace(month=1, day=1), today
        return first, today    # this_month

    # -- derived periods ---------------------------------------------------------------------------
    @property
    def days(self):
        return (self.end - self.start).days + 1

    @property
    def previous(self):
        """The period right before this one: the month before for the month presets, else the same length."""
        if self.period in ('this_month', 'last_month'):
            return self.start - relativedelta(months=1), self.end - relativedelta(months=1)
        return self.start - relativedelta(days=self.days), self.start - relativedelta(days=1)

    @property
    def last_year(self):
        """The same dates one year earlier (29 February becomes 28 February)."""
        return self.start - relativedelta(years=1), self.end - relativedelta(years=1)

    # -- presentation ------------------------------------------------------------------------------
    @property
    def period_label(self):
        if self.period == 'custom':
            return f'{self.start:%d.%m.%Y} – {self.end:%d.%m.%Y}'
        return str(dict(PRESETS)[self.period])

    @property
    def range_label(self):
        return f'{self.start:%d.%m.%Y} – {self.end:%d.%m.%Y}'

    @property
    def scope_label(self):
        return str(dict(SCOPES)[self.scope])

    def as_params(self, **overrides):
        """Query parameters that reproduce these filters. Defaults are left out to keep URLs short."""
        params = {}
        if self.period == 'custom':
            params.update({'period': 'custom', 'from': self.start.isoformat(), 'to': self.end.isoformat()})
        elif self.period != self.default_period:
            params['period'] = self.period
        if self.currency != DEFAULT_CURRENCY:
            params['currency'] = self.currency
        if self.scope != 'all':
            params['scope'] = self.scope
        for key, value in overrides.items():
            if value in (None, ''):
                params.pop(key, None)
            else:
                params[key] = value
        if overrides.get('period') and overrides['period'] != 'custom':
            params.pop('from', None)
            params.pop('to', None)
        return params

    def query(self, **overrides):
        """Query string ("" or "?a=b") for links that keep the current filters."""
        encoded = urlencode(self.as_params(**overrides), doseq=True)
        return f'?{encoded}' if encoded else ''

    def carry(self):
        """Parameters carried from tab to tab: an explicit period stays, a tab's own default does not."""
        return self.query()

    def preset_links(self):
        return [{'key': key, 'label': label, 'active': key == self.period, 'query': self.query(period=key) or '?period=' + key}
                for key, label in PRESETS]

    def currencies(self):
        return [{'code': code, 'active': code == self.currency} for code in CurrencyChoice.values]

    def scopes(self):
        return [{'key': key, 'label': label, 'active': key == self.scope} for key, label in SCOPES]

    @property
    def symbol(self):
        """Short sign of the report currency for amounts on the page."""
        return {'EUR': '€', 'BGN': 'лв.', 'USD': '$'}.get(self.currency, self.currency)

    def subtitle(self):
        return _('%(period)s · %(scope)s · %(currency)s') % {
            'period': self.range_label, 'scope': self.scope_label.lower(), 'currency': self.currency}
