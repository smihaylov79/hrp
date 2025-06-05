from django.urls import path
from django.contrib.auth import views as auth_views
from .views import *

urlpatterns = [
    path('login/', custom_login, name='login'),
    path('logout/', custom_logout, name='logout'),
    path('register/', register, name='register'),
    path('profile/', profile_view, name='profile'),
]
