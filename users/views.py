from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from .forms import RegistrationForm, ProfileUpdateForm, HouseholdCreationForm, JoinHouseholdForm
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.views.generic import TemplateView, DetailView
from .models import HouseholdMembership, HouseHold, CustomUser
from .utils import merge_user_inventory_to_household


def register(request):
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect(request.GET.get('next') or 'home')
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
            return redirect(request.GET.get('next') or 'home')
    else:
        form = AuthenticationForm()

    return render(request, "users/login.html", {"form": form})


@login_required
def profile_view(request):
    user = request.user
    user_household = user.household
    profile_form = ProfileUpdateForm(instance=user)
    password_form = PasswordChangeForm(user)
    household_form = HouseholdCreationForm()
    join_form = JoinHouseholdForm()

    pending_requests = HouseholdMembership.objects.filter(user=user, status='pending')

    owned_households = HouseHold.objects.filter(owner=user)
    incoming_requests = HouseholdMembership.objects.filter(
        household__in=owned_households,
        status='pending'
    )

    if request.method == "POST":
        if "update_profile" in request.POST:
            profile_form = ProfileUpdateForm(request.POST, instance=user)
            if profile_form.is_valid():
                profile_form.save()
                return redirect("profile")

        elif "change_password" in request.POST:
            password_form = PasswordChangeForm(user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                return redirect("profile")

        elif 'create_household' in request.POST:
            household_form = HouseholdCreationForm(request.POST)
            if household_form.is_valid():
                household = household_form.save(commit=False)
                household.owner = user
                household.save()
                user.household = household
                user.save()
                merge_user_inventory_to_household(user, household)
                return redirect("profile")

        elif 'join_household' in request.POST:
            join_form = JoinHouseholdForm(request.POST)
            if join_form.is_valid():
                nickname = join_form.cleaned_data['nickname']
                try:
                    household = HouseHold.objects.get(nickname=nickname)
                    HouseholdMembership.objects.create(user=user, household=household, status='pending')
                    messages.success(request, "Заявката за присъединяване е изпратена.")
                except HouseHold.DoesNotExist:
                    messages.error(request, "Не съществува домакинство с този псевдоним.")

                return redirect("profile")

        elif "approve_request" in request.POST or "reject_request" in request.POST:
            membership_id = request.POST.get("membership_id")
            try:
                membership = HouseholdMembership.objects.get(id=membership_id)
                if membership.household.owner == user:
                    if "approve_request" in request.POST:
                        membership.status = 'approved'
                        membership.save()
                        membership.user.household = membership.household
                        membership.user.save()
                        merge_user_inventory_to_household(membership.user, membership.household)
                        messages.success(request,
                             f"{membership.user.get_full_name()} е одобрен за домакинство {membership.household.name}. Продуктите са добавени!")
                    else:
                        membership.status = 'rejected'
                        membership.save()
                        messages.warning(request,
                             f"{membership.user.get_full_name()} е отхвърлен за домакинство {membership.household.nickname}.")
                else:
                    messages.error(request, "Нямате права да управлявате тази заявка.")
            except HouseholdMembership.DoesNotExist:
                messages.error(request, "Заявката не беше намерена.")
            return redirect("profile")

    return render(request, "users/profile.html", {
        "profile_form": profile_form,
        "password_form": password_form,
        'household_form': household_form,
        'join_form': join_form,
        'pending_requests': pending_requests,
        'incoming_requests': incoming_requests,
        'user_household': user_household,
    })


class PleaseLoginView(TemplateView):
    template_name = "users/please_login.html"


class HouseholdView(DetailView):
    model = HouseHold
    template_name = "users/household.html"
    context_object_name = "household"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["members"] = CustomUser.objects.filter(household=self.object)
        return context


@login_required
def leave_household(request):
    user = request.user
    if user.household:
        HouseholdMembership.objects.filter(user=user, household=user.household).delete()
        user.household = None
        user.save()
        messages.success(request, "Успешно напуснахте домакинството.")
    return redirect("profile")


@login_required
def remove_member(request, user_id):
    household = request.user.household
    if household and request.user == household.owner:
        target_user = get_object_or_404(CustomUser, id=user_id)
        if target_user.household == household:
            HouseholdMembership.objects.filter(user=target_user, household=household).delete()
            target_user.household = None
            target_user.save()
            messages.success(request, f"{target_user.first_name} е премахнат от домакинството.")
    return redirect("household", pk=household.pk)
