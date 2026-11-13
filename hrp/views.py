from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from . import dashboard
from .utils import collect_weather_data


class HomeView(TemplateView):
    template_name = 'home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user

        if user.is_authenticated:
            context.update(dashboard.build(user))
        else:
            context.update({'tasks_today': 0, 'tasks_overdue': 0, 'task_total': 0})

        weather_data, error_message, current_time, rate = collect_weather_data(self.request)
        context.update(
            {'weather_data': weather_data,
             'weather_error': error_message,
             'now': current_time,
             'rate': rate})

        return context


class SearchView(LoginRequiredMixin, TemplateView):
    """Search box in the top bar: the user's bought products, recipes and tasks."""
    template_name = 'search.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('q', '').strip()
        results = dashboard.search(self.request.user, query)
        context.update(results)
        context['search_query'] = query
        context['result_count'] = sum(len(rows) for rows in results.values())
        return context
