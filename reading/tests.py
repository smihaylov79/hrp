from django.urls import reverse

from hrp.testing import HrpTestCase

from .models import Author, Genre, UserBook, UserLibrary


class ReadingAccessTests(HrpTestCase):

    def test_ajax_endpoints_require_login(self):
        for name, data in [('add_author_ajax', {'name': 'Вазов'}), ('add_genre_ajax', {'name': 'Роман'}),
                           ('add_library_ajax', {'name': 'Моята'})]:
            with self.subTest(view=name):
                self.assertLoginRequired(reverse(name), method='post', data=data)
        self.assertFalse(Author.objects.exists())
        self.assertFalse(Genre.objects.exists())
        self.assertFalse(UserLibrary.objects.exists())

    def test_note_endpoints_require_login(self):
        for name in ['upload_note_image', 'save_extracted_comment']:
            with self.subTest(view=name):
                self.assertLoginRequired(reverse(name, kwargs={'source': 'user', 'book_id': 1}), method='post',
                                         data={'edited_text': 'x'})

    def test_logged_in_user_can_add_library(self):
        self.client.force_login(self.alice)
        response = self.client.post(reverse('add_library_ajax'), {'name': 'Моята'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(UserLibrary.objects.get().user, self.alice)

    def test_foreign_library_is_404(self):
        library = UserLibrary.objects.create(name='На Боб', user=self.bob)
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(reverse('library_detail', args=[library.pk])).status_code, 404)
        self.client.force_login(self.bob)
        self.assertEqual(self.client.get(reverse('library_detail', args=[library.pk])).status_code, 200)

    def test_notes_of_a_foreign_book_cannot_be_changed(self):
        book = UserBook.objects.create(title='Под игото', user=self.bob,
                                       author=Author.objects.create(name='Иван Вазов'))
        self.client.force_login(self.alice)
        url = reverse('save_extracted_comment', kwargs={'source': 'user', 'book_id': book.pk})
        self.assertEqual(self.client.post(url, {'edited_text': 'хак'}).status_code, 404)
        book.refresh_from_db()
        self.assertFalse(book.notes)
