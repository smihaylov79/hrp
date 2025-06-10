from django.shortcuts import render, redirect, get_object_or_404
from .models import Category, Thread, Post
from django.contrib.auth.decorators import login_required
from .forms import *

# Create your views here.



@login_required
def forum_home(request):
    categories = Category.objects.all()
    return render(request, "forum/forum_home.html", {"categories": categories})


@login_required
def thread_detail(request, thread_id):
    thread = Thread.objects.get(id=thread_id)
    posts = Post.objects.filter(thread=thread)
    return render(request, "forum/thread_detail.html", {"thread": thread, "posts": posts})


@login_required
def create_category(request):
    """ Allow superusers to create categories """
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


@login_required
def category_threads(request, category_id):
    """ Display threads in a specific category """
    category = get_object_or_404(Category, id=category_id)
    threads = Thread.objects.filter(category=category).order_by("-last_activity")

    return render(request, "forum/category_threads.html", {"category": category, "threads": threads})


@login_required
def create_thread(request, category_id):
    """ Allow users to create a new thread in a category """
    category = get_object_or_404(Category, id=category_id)

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


@login_required
def thread_detail(request, thread_id):
    """ Display posts within a thread & allow replies """
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

    # Update thread views count
    thread.views += 1
    thread.save()

    return render(request, "forum/thread_detail.html", {"thread": thread, "posts": posts, "form": form})


def get_categories(request):
    """ Ensures categories are accessible in all forum pages """
    return {"categories": Category.objects.all()}