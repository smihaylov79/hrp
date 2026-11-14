from datetime import date

from django.utils import timezone

from hrp.testing import HrpTestCase

from .models import Task


class TaskDefaultsTests(HrpTestCase):
    def test_new_task_is_due_today_in_local_time(self):
        task = Task.objects.create(user=self.alice, title='Тест')
        self.assertIsInstance(task.due_date, date)
        self.assertEqual(task.due_date, timezone.localdate())
        task.refresh_from_db()
        self.assertEqual(task.due_date, timezone.localdate())
