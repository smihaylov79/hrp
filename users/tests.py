from django.test import TestCase, RequestFactory
from django.urls import reverse
from .models import CustomUser, HouseHold
from .forms import RegistrationForm
# Create your tests here.


class RegistrationFormTest(TestCase):
    def test_valid_form_creates_user(self):
        form_data = {
            'email': 'test@user.com',
            'first_name': 'test',
            'last_name': 'user',
            'password1': 'Ineedstrongpassord123!@',
            'password2': 'Ineedstrongpassord123!@',
        }
        form = RegistrationForm(data=form_data)
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.email, 'test@user.com')
        self.assertTrue(user.check_password('Ineedstrongpassord123!@'))


class ProfileUpdateTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = CustomUser.objects.create_user(
            email='test@user.com',
            first_name='test',
            last_name='user',
            password='Ineedstrongpassord123!@',
        )
        self.client.force_login(self.user)

    def test_update_phone_number(self):
        response = self.client.post(reverse('profile'), {
            'update_profile': True,
            'first_name': 'test',
            'last_name': 'user',
            'email': 'test@user.com',
            'phone_number': '1234567890'
        })

        self.user.refresh_from_db()
        self.assertEqual(self.user.phone_number, '1234567890')


class HouseholdCreationTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = CustomUser.objects.create_user(
            email='test@user.com',
            first_name='test',
            last_name='user',
            password='Ineedstrongpassord123!@',
        )
        self.client.force_login(self.user)

    def test_create_household(self):
        response = self.client.post(reverse('profile'), {
            'create_household': True,
            'name': 'Test Household',
            'nickname': 'test_household',
            'address': 'test address 15'
        })

        household = HouseHold.objects.get(nickname='test_household')
        self.user.refresh_from_db()

        self.assertEqual(household.owner, self.user)
        self.assertEqual(self.user.household, household)


class LeaveHouseholdTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='test@user.com',
            first_name='test',
            last_name='user',
            password='Ineedstrongpassord123!@',
        )
        self.household = HouseHold.objects.create(
            name='Test Household',
            nickname='test_household',
            address='test address 15',
            owner=self.user
        )
        self.user.household = self.household
        self.user.save()
        self.client.force_login(self.user)

    def test_leave_household(self):
        response = self.client.get(reverse('leave_household'))

        self.user.refresh_from_db()
        self.assertIsNone(self.user.household)
