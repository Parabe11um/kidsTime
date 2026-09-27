from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("profile/", views.profile, name="profile"),
    path("health/", views.health, name="health"),
    path("robots.txt", views.robots_txt, name="robots_txt"),
]
