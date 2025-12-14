from django.db import models
from django.conf import settings

from shopping.models import CurrencyChoice
from users.models import CustomUser


class IncomeType(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Income(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="incomes")
    income_type = models.ForeignKey(IncomeType, on_delete=models.PROTECT, related_name="incomes")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CurrencyChoice.choices, default=CurrencyChoice.BGN)
    date_received = models.DateField()
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-date_received"]

    def __str__(self):
        return f"{self.income_type.name} - {self.amount} {self.currency}"

