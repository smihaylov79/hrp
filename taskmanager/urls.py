from django.urls import path
from .views import *

urlpatterns = [
    path('', TaskListView.as_view(), name='task_list'),
    path('create/', TaskCreateView.as_view(), name='create_task'),
    path('update/<int:pk>/', TaskUpdateView.as_view(), name='update_task'),
    path('toggle/<int:pk>/', ToggleTaskView.as_view(), name='toggle_task'),
    path('calendar/', EventListView.as_view(), name='calendar'),
    path('events/json/', event_json, name='event_json'),
    path('events/create/', EventCreateView.as_view(), name='create_event'),
]
