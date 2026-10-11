from django.urls import path

from . import views

app_name = "favorites"

urlpatterns = [
    path("save/<int:event_id>/", views.set_favorite, name="set"),
    path("merge/", views.merge_favorites, name="merge"),
    path("", views.favorite_list, name="list"),
    path("cards/", views.favorite_cards, name="cards"),
    path("toggle/<int:event_id>/", views.toggle_favorite, name="toggle"),
]
