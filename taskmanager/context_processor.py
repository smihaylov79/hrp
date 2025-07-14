from .models import Task

def incomplete_tasks(request):
    count = 0
    if request.user.is_authenticated:
        count = Task.objects.filter(user=request.user, completed=False).count()
    return {'incomplete_tasks': count}