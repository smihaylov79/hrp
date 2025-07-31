from django.contrib import admin
from .models import *
from datetime import date

# Register your models here.

@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display = ('name', 'open_time', 'close_time', 'get_time_until_event')

    def get_time_until_event(self, obj):
        now_local = timezone.now()  # Aware datetime in local timezone
        local_tz = timezone.get_current_timezone()
        market_tz = pytz.timezone(obj.time_zone)

        # Convert to market time
        now_market = now_local.astimezone(market_tz)
        current_time = now_market.time()

        # Build today's market open/close datetime
        today_market = now_market.date()
        open_dt_market = market_tz.localize(datetime.combine(today_market, obj.open_time))
        close_dt_market = market_tz.localize(datetime.combine(today_market, obj.close_time))

        if obj.open_time <= current_time <= obj.close_time:
            # Market is open → time until close
            label = "Closes in"
            target_dt = close_dt_market
        else:
            label = "Opens in"
            # Opens later today?
            if current_time < obj.open_time:
                target_dt = open_dt_market
            else:
                # Opens tomorrow
                tomorrow_market = today_market + timedelta(days=1)
                target_dt = market_tz.localize(datetime.combine(tomorrow_market, obj.open_time))

        # Convert target datetime to local timezone
        target_dt_local = target_dt.astimezone(local_tz)
        delta = target_dt_local - now_local

        if delta.total_seconds() < 0:
            return "Event passed"

        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)
        return f"{label} {hours}h {minutes}m"

    get_time_until_event.short_description = "Time Until Event"

@admin.register(MarketHoliday)
class MarketHolidayAdmin(admin.ModelAdmin):
    ...
