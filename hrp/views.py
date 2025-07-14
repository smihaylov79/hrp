from django.shortcuts import render


# def home(request):
#     return render(request, 'home.html')

from datetime import date, datetime, time

from django.views.generic import TemplateView

from taskmanager.models import Task, Event

class HomeView(TemplateView):
    template_name = 'home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user

        if user.is_authenticated:
            today = date.today()
            now=datetime.now()
            end_of_day=datetime.combine(now.date(), time(23, 59, 59))
            tasks_today = Task.objects.filter(user=user, due_date=today, completed=False)
            tasks_overdue = Task.objects.filter(user=user, due_date__lt=today, completed=False)

            context['tasks_today'] = tasks_today
            context['tasks_overdue'] = tasks_overdue
            context['task_total'] = tasks_today.count() + tasks_overdue.count()

            context['events_today'] = Event.objects.filter(user=user,
                                                           start_datetime__gte=now,
                                                           start_datetime__lte=end_of_day)

        else:
            context['tasks_today'] = []
            context['tasks_overdue'] = []
            context['task_total'] = 0
        return context
