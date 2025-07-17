from django.urls import path
from django.contrib.auth import views as auth_views
from .views import *

urlpatterns = [
    path('login/', custom_login, name='login'),
    path('logout/', custom_logout, name='logout'),
    path('register/', register, name='register'),
    path('profile/', profile_view, name='profile'),
    path('please-login/', PleaseLoginView.as_view(), name='please_login'),
    path('household/<int:pk>', HouseholdView.as_view(), name='household'),
    path('leave/', leave_household, name='leave_household'),
    path('remove-member/<int:user_id>', remove_member, name='remove_member')
]
