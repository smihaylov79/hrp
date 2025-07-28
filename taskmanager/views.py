from datetime import date, datetime

from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, CreateView, UpdateView, View
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from taskmanager.models import Task, Event
from .forms import TaskForm, EventForm

# Create your views here.


class TaskListView(LoginRequiredMixin, ListView):
    model = Task
    template_name = 'taskmanager/task_list.html'
    context_object_name = 'tasks'

    def get_queryset(self):
        return Task.objects.filter(user=self.request.user).order_by('due_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['today'] = date.today()
        return context


class TaskCreateView(LoginRequiredMixin, CreateView):
    model = Task
    form_class = TaskForm
    template_name = 'taskmanager/create_task.html'
    success_url = reverse_lazy('task_list')

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class TaskUpdateView(LoginRequiredMixin, UpdateView):
    model = Task
    form_class = TaskForm
    template_name = 'taskmanager/update_task.html'
    success_url = reverse_lazy('task_list')

    def get_queryset(self):
        return Task.objects.filter(user=self.request.user).order_by('due_date')


class ToggleTaskView(LoginRequiredMixin, View):
    def post(self, request, pk):
        task = get_object_or_404(Task, pk=pk, user=request.user)
        task.completed = not task.completed
        task.save()
        return redirect('task_list')


class EventListView(LoginRequiredMixin, ListView):
    model = Event
    template_name = 'taskmanager/calendar.html'
    context_object_name = 'calendar'
    def get_queryset(self):
        return Event.objects.filter(user=self.request.user)


def event_json(request):
    events = []
    if request.user.is_authenticated:
        for e in Event.objects.filter(user=request.user):
            events.append({
                "title": e.title,
                "start": e.start_datetime.isoformat(),
                "end": e.end_datetime.isoformat(),
                "allDay": e.all_day,
            })
    return JsonResponse(events, safe=False)


class EventCreateView(LoginRequiredMixin, CreateView):
    model = Event
    form_class = EventForm
    template_name = 'taskmanager/create_event.html'
    success_url = reverse_lazy('calendar')

    def get_initial(self):
        initial = super().get_initial()
        date_str = self.request.GET.get('date')
        if date_str:
            try:
                selected_date = datetime.strptime(date_str, '%Y-%m-%d')
                initial['start_datetime'] = selected_date
                initial['end_datetime'] = selected_date
            except ValueError:
                pass
        return initial

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)
