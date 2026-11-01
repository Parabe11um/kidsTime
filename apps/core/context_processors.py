from django.conf import settings

from apps.catalog.models import Event


def runtime_settings(request):
    favorite_ids = []
    avatar_url = ""
    if request.user.is_authenticated:
        account = getattr(request.user, "account", None)
        if account and account.avatar:
            avatar_url = account.avatar.url
        favorite_ids = list(
            request.user.favorites.filter(event__in=Event.objects.visible())
            .values_list("event_id", flat=True)[:100]
        )
    return {
        "YANDEX_MAPS_API_KEY": settings.YANDEX_MAPS_API_KEY,
        "account_favorite_ids": favorite_ids,
        "account_avatar_url": avatar_url,
    }
