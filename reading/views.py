from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import JsonResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
import os
import pytesseract
pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_CMD")
from PIL import Image


from .models import Author, Genre, Book, UserLibrary, UserBook
from .forms import AuthorForm, GenreForm, BookForm, UserBookForm, LibraryForm, UserBookOCRForm
from users.models import CustomUser
from .helpers import from_user_to_shared, from_shared_to_user


def reading_home(request):
    books = Book.objects.all().order_by('title')
    context = {
        'books': books,
    }
    return render(request, 'reading/reading_home.html', context)


# def book_detail(request, book_id):
#     book = get_object_or_404(UserBook, pk=book_id)
#     context = {
#         'book': book,
#     }
#     return render(request, 'reading/book_detail.html', context)


@login_required
def user_library(request):
    user = request.user
    book_form = UserBookForm()
    author_form = AuthorForm()
    genre_form = GenreForm()
    library_form = LibraryForm()

    author = request.GET.get('author')
    genre = request.GET.get('genre')
    title = request.GET.get('title')

    user_books = UserBook.objects.filter(user=request.user, library__isnull=True)

    if author:
        user_books = user_books.filter(author__name__icontains=author)
    if genre:
        user_books = user_books.filter(genre__name__icontains=genre)
    if title:
        user_books = user_books.filter(title__icontains=title)

    libraries = UserLibrary.objects.filter(user=user).annotate(books_count=Count('library_book')).order_by(
        '-books_count')
    book_form.fields['library'].queryset = libraries

    if request.method == 'POST':
        form = UserBookForm(request.POST, request.FILES)
        if form.is_valid():
            user_book = form.save(commit=False)
            user_book.user = user
            user_book.shared_from = user
            user_book.save()

            if user_book.shared:
                Book.objects.create(
                    title=user_book.title,
                    author=user_book.author,
                    genre=user_book.genre,
                    description=user_book.description,
                    published_date=user_book.published_date,
                    cover_image=user_book.cover_image,
                    shared_from=user
                )
            return redirect('user_library')

    context = {
        'libraries': libraries,
        'user_books_without_library': user_books,
        'form': book_form,
        'author_form': author_form,
        'genre_form': genre_form,
        'library_form': library_form,
        'author': author,
        'genre': genre,
        'title': title,

    }
    return render(request, 'reading/user_library.html', context)


@login_required
def library_detail(request, library_id):
    user = request.user
    library = UserLibrary.objects.get(pk=library_id)
    library_books = UserBook.objects.filter(library=library, user=user).order_by('-rating')
    context = {
        'library': library,
        'library_books': library_books,
    }
    return render(request, 'reading/library_detail.html', context)


def add_author_ajax(request):
    if request.method == 'POST':
        form = AuthorForm(request.POST, request.FILES)
        if form.is_valid():
            author = form.save()
            return JsonResponse({'id': author.id, 'name': author.name})
    return JsonResponse({'error': 'Invalid data'}, status=400)


def add_genre_ajax(request):
    if request.method == 'POST':
        form = GenreForm(request.POST)
        if form.is_valid():
            genre = form.save()
            return JsonResponse({'id': genre.id, 'name': genre.name})
    return JsonResponse({'error': 'Invalid data'}, status=400)


def add_library_ajax(request):
    if request.method == 'POST':
        form = LibraryForm(request.POST)
        if form.is_valid():
            library = form.save(commit=False)
            library.user = request.user
            library.save()
            return JsonResponse({'id': library.id, 'name': library.name})
    return JsonResponse({'error': 'Invalid data'}, status=400)


def book_detail(request, source, book_id):
    user = request.user
    if source == 'user' and user.is_authenticated:
        book = get_object_or_404(UserBook, pk=book_id, user=user)
        if isinstance(book, UserBook) and book.library:
            library = book.library
        else:
            library = None

        if request.method == 'POST':
            from_user_to_shared(request, book)

            return redirect('user_library')

    elif source == 'shared':
        book = get_object_or_404(Book, pk=book_id)

        library = None

        if request.method == 'POST':
            from_shared_to_user(request, book)
            return redirect('user_library')

    else:
        raise Http404("Invalid book source")

    library_form = LibraryForm()
    comments = {}
    book_comments = UserBook.objects.filter(title=book.title)
    if book_comments:
        for b in book_comments:
            if b.comments:
                comments[b.user.first_name] = b.comments

    user_book = UserBook.objects.filter(title=book.title, user=request.user).first()
    user_book_id = user_book.id if user_book else None

    context = {
        'book': book,
        'library': library,
        'libraries': UserLibrary.objects.filter(user=user),  # Needed for the dropdown
        'library_id': library.id if library else None,
        'library_form': library_form,
        'source': source,
        'request': request,
        'comments': comments,
        'user_book_id': user_book_id,
    }
    return render(request, 'reading/book_detail.html', context)


def upload_note_image(request, source, book_id):
    user = request.user

    if source == 'user' and user.is_authenticated:
        book = get_object_or_404(UserBook, pk=book_id, user=user)
    else:
        raise Http404("Invalid book source")

    if request.method == 'POST' and request.FILES.get('image'):
        image = Image.open(request.FILES['image'])
        selected_lang = request.POST.get('language', 'eng')  # Default to English

        extracted_text = pytesseract.image_to_string(image, lang=selected_lang)
        book.notes = (book.notes or '') + f"\n\n[OCR-{selected_lang}]: {extracted_text.strip()}"
        book.save()

    return redirect('book_detail', source='user', book_id=book.id)


def save_extracted_comment(request, source, book_id):
    user = request.user

    if source == 'user' and user.is_authenticated:
        book = get_object_or_404(UserBook, pk=book_id, user=user)
    else:
        raise Http404("Invalid book source")

    if request.method == 'POST':
        edited_text = request.POST.get('edited_text', '').strip()
        if edited_text:
            book.notes = (book.notes or '') + f"\n\n[OCR]: {edited_text}"
            book.save()

    return redirect('book_detail', source='user', book_id=book.id)

