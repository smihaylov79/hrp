from datetime import datetime

from django.db import models
from django.utils import timezone

from users.models import CustomUser


# Create your models here.


class PriorityLevel(models.TextChoices):
    LOW = 'Нисък', 'Нисък'
    MEDIUM = 'Нормален', 'Нормален'
    HIGH = 'Висок', 'Висок'


class Task(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    due_date = models.DateField(default=timezone.now)
    priority = models.CharField(max_length=10, choices=PriorityLevel.choices, default=PriorityLevel.MEDIUM)
    completed = models.BooleanField(default=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

    def __str__(self):
        return self.title


class Event(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    location = models.CharField(max_length=100, blank=True, null=True)
    all_day = models.BooleanField(default=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

    def __str__(self):
        return self.title
