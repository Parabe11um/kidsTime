from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.event_list, name="event_list"),
    path("map/", views.event_map, name="event_map"),
    path("walk/", views.walk_builder, name="walk_builder"),
    path("api/map/", views.map_events_api, name="map_events_api"),
    path("api/walk/", views.walk_events_api, name="walk_events_api"),
    path("<slug:slug>/", views.event_detail, name="event_detail"),
]
