from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone

from reading.forms import UserBookForm
from reading.models import UserLibrary, Book, UserBook


def move_book_to_library(user_book, new_library):
    try:
        entry = UserLibrary.objects.get(user_book=user_book)
        entry.library = new_library
        entry.updated_at = timezone.now()
        entry.save()
    except UserLibrary.DoesNotExist:
        # If the book wasn't in any library, create a new entry
        UserLibrary.objects.create(
            user_book=user_book,
            library=new_library,
            is_read=False  # or default values
        )


def from_user_to_shared(request, book):
    user = request.user
    book.title = request.POST.get('title')
    book.notes = request.POST.get('notes')
    book.comments = request.POST.get('comments')
    book.is_read = 'is_read' in request.POST
    book.shared = 'shared' in request.POST
    book.rating = request.POST.get('rating', None)

    if 'cover_image' in request.FILES:
        book.cover_image = request.FILES['cover_image']

    library_id = request.POST.get('library', None)

    if library_id:
        book.library = get_object_or_404(UserLibrary, pk=library_id)
    else:
        book.library = None

    book.save()
    if book.shared:
        Book.objects.get_or_create(
            title=book.title,
            defaults={
                'author': book.author,
                'genre': book.genre,
                'description': book.description,
                'published_date': book.published_date,
                'cover_image': book.cover_image,
                'shared_from': user
            }
        )
    else:
        Book.objects.filter(title=book.title, shared_from=request.user).delete()

    if book.library:
        redirect_url = reverse("library_detail", kwargs={"library_id": book.library.id})
    else:
        redirect_url = reverse("user_library")  # Or any fallback view you prefer
    return redirect(redirect_url)


def from_shared_to_user(request, book):
    user = request.user
    UserBook.objects.get_or_create(
        user=user,
        title=book.title,
        defaults={
            'author': book.author,
            'genre': book.genre,
            'description': book.description,
            'published_date': book.published_date,
            'cover_image': book.cover_image,
            'shared': True,
            'shared_from': book.shared_from
        }
    )
    return redirect(reverse("user_library"))