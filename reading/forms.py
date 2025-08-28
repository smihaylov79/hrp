from django import forms
from .models import Author, Genre, Book, UserBook, UserLibrary


class AuthorForm(forms.ModelForm):
    class Meta:
        model = Author
        fields = ['name', 'bio', 'birth_date', 'photo']


class GenreForm(forms.ModelForm):
    class Meta:
        model = Genre
        fields = ['name', 'description']


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ['title', 'author', 'genre', 'description', 'published_date', 'cover_image']


class UserBookForm(forms.ModelForm):
    class Meta:
        model = UserBook
        fields = ['title', 'author', 'genre', 'description', 'published_date', 'cover_image', 'shared', 'library']
        labels = {
            'title': 'Заглавие',
            'author': 'Автор',
            'genre': 'Жанр',
            'description': 'Сюжет',
            'published_date': 'Дата на издаване',
            'cover_image': 'Корица',
            'shared': 'споделена',
            'library': 'Библиотека',
        }
        widgets = {
            'published_date': forms.DateInput({'name': 'date', 'class': 'form-control', 'type': 'date'}),

        }


class LibraryForm(forms.ModelForm):
    class Meta:
        model = UserLibrary
        fields = ['name', 'description']


class UserBookOCRForm(forms.ModelForm):
    image = forms.ImageField(required=True)

    class Meta:
        model = UserBook
        fields = ['image']