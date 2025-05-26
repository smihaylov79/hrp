from django.urls import path
from .views import *

urlpatterns = [
    path("", entertainment_home, name="entertainment_home"),
    path("travel/", travel, name="travel"),
    path("reading/", reading, name="reading"),
    path("movies/", movies, name="movies"),
    path("games/", games, name="games"),
    path("games/calculator/", game_calculator, name="game_calculator"),
]
