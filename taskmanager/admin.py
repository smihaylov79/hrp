from django.contrib import admin
from .models import *
# Register your models here.


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('user', 'due_date', 'title', 'priority', 'completed', )
    list_filter = ('completed', 'priority', 'due_date', )


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'start_datetime', )
    list_filter = ('start_datetime', )