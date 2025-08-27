from django.db.models import Avg
from django import template

from reading.models import UserBook

register = template.Library()


@register.filter
def calculate_rating(value):
    all_ratings = UserBook.objects.filter(title=value)
    rating = all_ratings.aggregate(avg_rating=Avg('rating'))['avg_rating']
    return round(rating, 1)


@register.filter
def check_book_in_user_books_name(value):
    book = UserBook.objects.filter(title=value).first()
    return book.title


@register.filter(name='check_book_in_user_books_id')
def check_book_in_user_books_id(value, user):
    book = UserBook.objects.filter(title=value, user=user).first()
    if book:
        return book.id
