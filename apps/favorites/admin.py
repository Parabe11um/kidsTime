from django.contrib import admin

from .models import Favorite


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "created_at")
    search_fields = ("user__username", "user__email", "event__title")
    autocomplete_fields = ("user", "event")
