from django.urls import reverse

from hrp.testing import HrpTestCase
from taskmanager.models import Task

from .models import Category, ThreadRequest


class ThreadRequestModerationTests(HrpTestCase):
    """Only staff may approve / reject a request for a new forum thread."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.carol.is_staff = True
        cls.carol.save(update_fields=['is_staff'])
        category = Category.objects.create(name='Общи')
        cls.thread_request = ThreadRequest.objects.create(title='Нова тема', category=category, requested_by=cls.alice)
        cls.url = reverse('edit_request_thread', args=[cls.thread_request.pk])

    def status(self):
        self.thread_request.refresh_from_db()
        return self.thread_request.status

    def test_anonymous_cannot_open_or_change_request(self):
        self.assertLoginRequired(self.url)
        self.assertLoginRequired(self.url, method='post', data={'status': 'approved'})
        self.assertEqual(self.status(), 'pending')

    def test_non_staff_cannot_change_request(self):
        self.client.force_login(self.bob)
        response = self.client.post(self.url, {'status': 'approved'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.status(), 'pending')

    def test_staff_can_approve_and_requester_is_notified(self):
        self.client.force_login(self.carol)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.client.post(self.url, {'status': 'approved', 'title': self.thread_request.title,
                                    'category': self.thread_request.category_id,
                                    'requested_by': self.alice.pk, 'description': ''})
        self.assertEqual(self.status(), 'approved')
        self.assertTrue(Task.objects.filter(user=self.alice).exists())

    def test_missing_request_is_404(self):
        self.client.force_login(self.carol)
        self.assertEqual(self.client.get(reverse('edit_request_thread', args=[99999])).status_code, 404)

    def test_anonymous_cannot_post_in_thread(self):
        from .models import Post, Thread
        thread = Thread.objects.create(category=self.thread_request.category, title='Тема', created_by=self.alice)
        url = reverse('thread_detail', args=[thread.pk])
        self.assertEqual(self.client.get(url).status_code, 200)          # reading stays public
        self.assertLoginRequired(url, method='post', data={'content': 'спам'})
        self.assertFalse(Post.objects.exists())
