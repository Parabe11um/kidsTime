from django.urls import path

from . import views

app_name = "favorites"

urlpatterns = [
    path("", views.favorite_list, name="list"),
    path("cards/", views.favorite_cards, name="cards"),
    path("toggle/<int:event_id>/", views.toggle_favorite, name="toggle"),
]
