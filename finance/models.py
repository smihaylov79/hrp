from django.db import models

# Create your models here.


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
