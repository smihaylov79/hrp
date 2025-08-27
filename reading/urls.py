from django.urls import path, include
from .views import *


urlpatterns = [
    path('', reading_home, name='reading_home'),
    path('library/', user_library, name='user_library'),
    path('ajax/add-author/', add_author_ajax, name='add_author_ajax'),
    path('ajax/add-genre/', add_genre_ajax, name='add_genre_ajax'),
    path('ajax/add-library/', add_library_ajax, name='add_library_ajax'),
    path('book-details/<str:source>/<int:book_id>', book_detail, name='book_detail'),
    path('library-detail/<int:library_id>', library_detail, name='library_detail'),
]