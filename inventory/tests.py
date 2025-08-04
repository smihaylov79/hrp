from datetime import date

from django.test import TestCase, RequestFactory
from django.urls import reverse

from shopping.models import ShoppingList
from taskmanager.models import Task
from users.forms import RegistrationForm
from users.models import CustomUser
from inventory.views import generate_shopping_list


# Create your tests here.

class ShoppingListGenerationTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = CustomUser.objects.create_user(email='test@user.com', password='Ineedstrongpassord123!@', first_name='test', last_name='user')

    def test_task_created(self):
        request = self.factory.get(reverse('shopping_list_view', args=[1]))
        request.user = self.user
        response = generate_shopping_list(request)
        task = Task.objects.filter(user=self.user).first()
        self.assertIsNotNone(task)
        self.assertIn('Пазаруване', task.title)
        self.assertEqual(task.due_date, date.today())