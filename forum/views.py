from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.urls import reverse

from taskmanager.models import Task
from .forms import CategoryForm, ThreadForm, PostForm, ThreadRequestForm, UpdateThreadRequestForm
from .models import Category, Thread, Post, ThreadRequest
from users.models import CustomUser

# Create your views here.


def forum_home(request):
    categories = Category.objects.all()
    return render(request, "forum/forum_home.html", {"categories": categories})


@login_required
def create_category(request):
    if not request.user.is_superuser:
        return redirect("forum_home")

    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("forum_home")
    else:
        form = CategoryForm()

    return render(request, "forum/create_category.html", {"form": form})


def category_threads(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    threads = Thread.objects.filter(category=category).order_by("-last_activity")

    return render(request, "forum/category_threads.html", {"category": category, "threads": threads})


@login_required
def create_thread(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if not request.user.is_staff:
        messages.warning(request, "Нямате право да създавате теми! Моля пуснете заявка към служител!")

        if request.method == "POST":
            request_form = ThreadRequestForm(request.POST)
            if request_form.is_valid():
                thread = request_form.save(commit=False)
                thread.category = category
                thread.requested_by = request.user
                thread.save()
                link = reverse("edit_request_thread", args=[thread.id])
                staff_users = CustomUser.objects.filter(is_staff=True)
                title = f"Искане за създаване на тема от {request.user.first_name}"
                description = (f"Искане за създаване на тема {thread.title} във форума в категория {thread.category.name}"
                               f" -> <a href='{link}'>Отиди на искането</a>'")
                due_date = thread.created_at
                for user in staff_users:
                    Task.objects.create(user=user, title=title, description=description, due_date=due_date)
                messages.success(request, 'Заявката беше пусната! Следи таблото със задачи за статус!')
                return redirect("forum_home")
        else:
            request_form = ThreadRequestForm()

        context = {
            "category": category,
            "request_form": request_form,
        }
        return render(request, "forum/request_thread.html", context)

    if request.method == "POST":
        form = ThreadForm(request.POST)
        if form.is_valid():
            thread = form.save(commit=False)
            thread.category = category
            thread.created_by = request.user
            thread.save()
            return redirect("category_threads", category_id=category.id)
    else:
        form = ThreadForm()

    return render(request, "forum/create_thread.html", {"form": form, "category": category})


def edit_request_thread(request, request_id):
    requested_thread = ThreadRequest.objects.get(id=request_id)
    form = UpdateThreadRequestForm(instance=requested_thread)

    if request.method == "POST":
        form = UpdateThreadRequestForm(request.POST, instance=requested_thread)
        if form.is_valid():
            updated_request = form.save()
            requested_user = updated_request.requested_by
            title = f"Промяна в статус на искане за отваряне на {updated_request.title} във форума"
            status = updated_request.get_status_display()
            description = f"Заявката за отваряна на тема е {status}"
            Task.objects.create(user=requested_user, title=title, description=description,)

            return redirect("forum_home")

    context = {
        'form': form,
        'requested_thread': requested_thread,
    }
    return render(request, "forum/edit_request_thread.html", context)


def thread_detail(request, thread_id):
    thread = get_object_or_404(Thread, id=thread_id)
    posts = Post.objects.filter(thread=thread).order_by("created_at")

    if request.method == "POST":
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.thread = thread
            post.author = request.user
            post.save()
            return redirect("thread_detail", thread_id=thread.id)
    else:
        form = PostForm()

    thread.views += 1
    thread.save()

    return render(request, "forum/thread_detail.html", {"thread": thread, "posts": posts, "form": form})


def get_categories(request):
    return {"categories": Category.objects.all()}