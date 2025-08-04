from django.contrib.auth.models import AbstractUser
from django.db import models
from .custom_managers import CustomUserManager


class HouseHold(models.Model):
    name = models.CharField(max_length=50)
    nickname = models.CharField(max_length=50, unique=True)
    address = models.CharField(max_length=50)

    owner = models.ForeignKey(
        'users.CustomUser', on_delete=models.CASCADE, related_name='owned_households'
    )

    def __str__(self):
        return self.name


class CustomUser(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone_number = models.CharField(max_length=15, blank=True, null=True)

    household = models.ForeignKey(HouseHold, on_delete=models.SET_NULL, blank=True, null=True, related_name='household')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = CustomUserManager()


class HouseholdMembership(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Заявен'),
        ('approved', 'Одобрен'),
        ('rejected', 'Отказан'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    household = models.ForeignKey(HouseHold, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'household')

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} - {self.household.name} ({self.status})"