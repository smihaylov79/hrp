from django.core.exceptions import ValidationError
from django.db import models
import pytz
from django.utils import timezone
from datetime import datetime, timedelta
from multiselectfield import MultiSelectField


# Create your models here.
DAYS_OF_WEEK = [
    ('MON', 'Monday'),
    ('TUE', 'Tuesday'),
    ('WED', 'Wednesday'),
    ('THU', 'Thursday'),
    ('FRI', 'Friday'),
    ('SAT', 'Saturday'),
    ('SUN', 'Sunday'),
]
TIME_ZONE_CHOICES = [
    ('Europe/Sofia', 'Europe/Sofia'),
    ('Europe/Berlin', 'Europe/Berlin'),
    ('Asia/Hong_Kong', 'Asia/Hong_Kong'),
    ('America/New_York', 'America/New_York'),
    ('Asia/Tokyo', 'Asia/Tokyo'),
    ('UTC', 'UTC'),
]


class SymbolsData(models.Model):
    date = models.DateField()
    symbol = models.CharField(max_length=20)
    company_name = models.CharField(max_length=100)
    open_price = models.FloatField()
    previous_close_price = models.FloatField()
    gap_open_price = models.FloatField()
    gap_open_percentage = models.FloatField()
    isin_number = models.CharField(max_length=50)
    details = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        abstract = True


class DailyData(SymbolsData):
    pass


class DailyDataInvest(SymbolsData):
    pass


class Market(models.Model):
    name = models.CharField(max_length=50, unique=True)
    time_zone = models.CharField(max_length=50, choices=TIME_ZONE_CHOICES, default='UTC')
    open_time = models.TimeField()
    close_time = models.TimeField()
    open_days = MultiSelectField(
        choices=DAYS_OF_WEEK,
        max_length=21,
        default=['MON', 'TUE', 'WED', 'THU', 'FRI']
    )

    def __str__(self):
        return self.name

    def time_until_event(self):
        market_tz = pytz.timezone(self.time_zone)
        local_tz = timezone.get_current_timezone()

        now_local = timezone.now()  # aware datetime in local timezone
        now_market = now_local.astimezone(market_tz)
        now_time = now_market.time()

        open_dt_market = datetime.combine(now_market.date(), self.open_time)
        close_dt_market = datetime.combine(now_market.date(), self.close_time)
        open_dt_market = market_tz.localize(open_dt_market)
        close_dt_market = market_tz.localize(close_dt_market)

        if self.open_time <= now_time <= self.close_time:
            event_dt = close_dt_market
        else:
            if now_time < self.open_time:
                event_dt = open_dt_market
            else:
                next_day = now_market + timedelta(days=1)
                event_dt = market_tz.localize(datetime.combine(next_day.date(), self.open_time))
        event_dt_local = event_dt.astimezone(local_tz)
        return event_dt_local - now_local

    def is_open_now(self):
        tz = pytz.timezone(self.time_zone)
        now = datetime.now(tz)
        today = now.date()
        if self.holidays.filter(date=today).exists():
            return False

        today_code = now.strftime('%a').upper()[:3]
        if today_code not in self.open_days:
            return False

        now_time = now.time()
        return self.open_time <= now_time <= self.close_time

    def clean(self):
        if self.open_time >= self.close_time:
            raise ValidationError("Market's open_time must be before close_time.")


class MarketHoliday(models.Model):
    market = models.ForeignKey('Market', on_delete=models.CASCADE, related_name='holidays')
    date = models.DateField()
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = ('market', 'date')


class SymbolsMapping(models.Model):
    isin_number = models.CharField(max_length=50, unique=True)
    trade_symbol = models.CharField(max_length=25, blank=True, null=True)
    invest_symbol = models.CharField(max_length=25, blank=True, null=True)
    official_symbol = models.CharField(max_length=25, blank=True, null=True)
    name_metatrader = models.CharField(max_length=250, blank=True, null=True)
    official_name = models.CharField(max_length=250, blank=True, null=True)
    industry = models.CharField(max_length=255, null=True, blank=True)
    sector = models.CharField(max_length=255, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)
    long_business_summary = models.TextField(null=True, blank=True)


class FundamentalsData(models.Model):
    extracted_date = models.DateField()
    symbol_mapping = models.ForeignKey(SymbolsMapping, on_delete=models.SET_NULL, null=True, blank=True)
    symbol_yahoo = models.CharField(max_length=25, blank=True, null=True)
    name = models.CharField(max_length=250, blank=True, null=True)

    full_time_employees = models.IntegerField(null=True, blank=True)

    # Dates
    ex_dividend_date = models.DateField(null=True, blank=True)
    last_dividend_date = models.DateField(null=True, blank=True)
    dividend_date = models.DateField(null=True, blank=True)
    earnings_call_timestamp_start = models.DateTimeField(null=True, blank=True)

    # Valuation & Price
    beta = models.FloatField(null=True, blank=True)
    forward_pe = models.FloatField(null=True, blank=True)
    market_cap = models.BigIntegerField(null=True, blank=True)
    fifty_two_week_low = models.FloatField(null=True, blank=True)
    fifty_two_week_high = models.FloatField(null=True, blank=True)
    price_to_sales_ttm = models.FloatField(null=True, blank=True)
    fifty_day_average = models.FloatField(null=True, blank=True)
    two_hundred_day_average = models.FloatField(null=True, blank=True)
    enterprise_value = models.BigIntegerField(null=True, blank=True)
    shares_outstanding = models.BigIntegerField(null=True, blank=True)
    current_price = models.FloatField(null=True, blank=True)
    price_to_book = models.FloatField(null=True, blank=True)

    # Growth & Earnings
    earnings_quarterly_growth = models.FloatField(null=True, blank=True)
    trailing_eps = models.FloatField(null=True, blank=True)
    forward_eps = models.FloatField(null=True, blank=True)
    eps_ttm = models.FloatField(null=True, blank=True)
    eps_forward = models.FloatField(null=True, blank=True)
    eps_current_year = models.FloatField(null=True, blank=True)
    price_eps_current_year = models.FloatField(null=True, blank=True)
    earnings_growth = models.FloatField(null=True, blank=True)
    revenue_growth = models.FloatField(null=True, blank=True)
    last_dividend_value = models.FloatField(null=True, blank=True)

    # Enterprise Ratios
    enterprise_to_revenue = models.FloatField(null=True, blank=True)
    enterprise_to_ebitda = models.FloatField(null=True, blank=True)

    # Price Change
    fifty_two_week_low_change_percent = models.FloatField(null=True, blank=True)
    fifty_two_week_high_change_percent = models.FloatField(null=True, blank=True)
    fifty_two_week_change = models.FloatField(null=True, blank=True)

    # Analyst Ratings
    target_high_price = models.FloatField(null=True, blank=True)
    target_low_price = models.FloatField(null=True, blank=True)
    target_median_price = models.FloatField(null=True, blank=True)
    recommendation_key = models.CharField(max_length=50, null=True, blank=True)
    number_of_analyst_opinions = models.IntegerField(null=True, blank=True)
    average_analyst_rating = models.CharField(max_length=50, null=True, blank=True)
    trailing_peg_ratio = models.FloatField(null=True, blank=True)

    # Financials
    total_cash = models.BigIntegerField(null=True, blank=True)
    total_cash_per_share = models.FloatField(null=True, blank=True)
    ebitda = models.BigIntegerField(null=True, blank=True)
    total_debt = models.BigIntegerField(null=True, blank=True)
    total_revenue = models.BigIntegerField(null=True, blank=True)
    revenue_per_share = models.FloatField(null=True, blank=True)
    gross_profits = models.BigIntegerField(null=True, blank=True)
    operating_cashflow = models.BigIntegerField(null=True, blank=True)

    # Margins
    gross_margins = models.FloatField(null=True, blank=True)
    ebitda_margins = models.FloatField(null=True, blank=True)
    operating_margins = models.FloatField(null=True, blank=True)

    # CEO Info (from nested companyOfficers)
    ceo_name = models.CharField(max_length=255, null=True, blank=True)
    ceo_age = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.name}"

