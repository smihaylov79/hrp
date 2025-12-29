from django.db import models

from income.models import IncomeType
from shopping.models import CurrencyChoice, MainCategory
from users.models import CustomUser, HouseHold


class Budget(models.Model):
    name = models.CharField(max_length=100, null=True, blank=True)
    creator = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="created_budgets"
    )
    household = models.ForeignKey(
        HouseHold,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="budgets"
    )
    date_from = models.DateField()
    date_to = models.DateField()
    currency = models.CharField(max_length=3, choices=CurrencyChoice.choices)
    submitted = models.BooleanField(default=False)
    approved = models.BooleanField(default=False)

    class Meta:
        ordering = ["-date_from"]

    def __str__(self):
        if self.household:
            return f"Household Budget {self.date_from} - {self.date_to}"
        return f"Budget of {self.creator} {self.date_from} - {self.date_to}"

    def scope_users(self):
        """Връща потребителите, за които важи бюджетът"""
        if self.household:
            return CustomUser.objects.filter(household=self.household)
        return [self.creator]

    def check_all_approved(self):
        required_users = set(self.scope_users().values_list("id", flat=True))

        approved_users = set(self.approvals.filter(approved=True).values_list("user_id", flat=True))
        return required_users == approved_users

    def reset_approvals(self):
        """Clear all approvals and mark budget as not approved."""

        self.approved = False
        self.save(update_fields=["approved"])
        self.approvals.update(approved=False, approved_at=None)


class BudgetItem(models.Model):
    budget = models.ForeignKey(
        Budget,
        on_delete=models.CASCADE,
        related_name="items"
    )
    category = models.ForeignKey(MainCategory, on_delete=models.CASCADE)
    planned_amount = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.category.name}: {self.planned_amount}"


class BudgetApproval(models.Model):
    budget = models.ForeignKey(
        Budget,
        on_delete=models.CASCADE,
        related_name="approvals"
    )
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    approved = models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("budget", "user")

    def __str__(self):
        return f"{self.user} approval for {self.budget}"


class BudgetIncomeItem(models.Model):
    budget = models.ForeignKey(
        Budget,
        on_delete=models.CASCADE,
        related_name="income_items"
    )
    income_type = models.ForeignKey(IncomeType, on_delete=models.CASCADE)
    planned_amount = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.income_type.name}: {self.planned_amount}"
