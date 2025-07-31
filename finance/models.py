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


class DailyData(models.Model):
    date = models.DateField()
    symbol = models.CharField(max_length=20)
    company_name = models.CharField(max_length=100)
    open_price = models.FloatField()
    previous_close_price = models.FloatField()
    gap_open_price = models.FloatField()
    gap_open_percentage = models.FloatField()
    isin_number = models.CharField(max_length=50)
    details = models.CharField(max_length=100, blank=True, null=True)


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
            # Market is open → time till close
            event_dt = close_dt_market
        else:
            # Market is closed → time till next open
            if now_time < self.open_time:
                event_dt = open_dt_market
            else:
                next_day = now_market + timedelta(days=1)
                event_dt = market_tz.localize(datetime.combine(next_day.date(), self.open_time))

        # Convert event time to local timezone
        event_dt_local = event_dt.astimezone(local_tz)
        return event_dt_local - now_local

    def is_open_now(self):
        tz = pytz.timezone(self.time_zone)
        now = datetime.now(tz)
        today = now.date()
        if self.holidays.filter(date=today).exists():
            return False  # Closed due to holiday

        today_code = now.strftime('%a').upper()[:3]
        if today_code not in self.open_days:
            return False  # Closed on this weekday

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