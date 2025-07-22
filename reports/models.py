from django.db import models

# Create your models here.


class ExchangeRate(models.Model):
    base_currency = models.CharField(max_length=3)
    target_currency = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=12, decimal_places=7)
    date_extracted = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = (('base_currency', 'target_currency', 'date_extracted'),)

    def __str__(self):
        return f'{self.base_currency} -> {self.target_currency} - {self.date_extracted}: {self.rate}'