from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from .forms import RegistrationForm
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from .forms import ProfileUpdateForm


def register(request):
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # Auto-login after registration
            return redirect('home')  # Redirect to homepage
    else:
        form = RegistrationForm()

    return render(request, "users/register.html", {"form": form})


def custom_logout(request):
    logout(request)
    return redirect('home')


def custom_login(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')  # Redirect to home page after login
    else:
        form = AuthenticationForm()

    return render(request, "users/login.html", {"form": form})


@login_required
def profile_view(request):
    user = request.user
    profile_form = ProfileUpdateForm(instance=user)
    password_form = PasswordChangeForm(user)

    if request.method == "POST":
        if "update_profile" in request.POST:  # Profile update form submission
            profile_form = ProfileUpdateForm(request.POST, instance=user)
            if profile_form.is_valid():
                profile_form.save()
                return redirect("profile")  # Redirect after profile update

        elif "change_password" in request.POST:  # Password change form submission
            password_form = PasswordChangeForm(user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)  # Keep user logged in
                return redirect("profile")  # Redirect after password change

    return render(request, "users/profile.html", {
        "profile_form": profile_form,
        "password_form": password_form
    })
