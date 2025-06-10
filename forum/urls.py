from django.urls import path
from .views import *

urlpatterns = [
    path("", forum_home, name="forum_home"),
    path("thread/<int:thread_id>/", thread_detail, name="thread_detail"),
    path("create-category/", create_category, name="create_category"),
    path("category/<int:category_id>/", category_threads, name="category_threads"),
    path("create-thread/<int:category_id>/", create_thread, name="create_thread"),
]