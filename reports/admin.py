from django.contrib import admin
from .models import *

# Register your models here.


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ('base_currency', 'target_currency', 'rate', 'date_extracted')
    list_filter = ('base_currency', 'date_extracted')


