from django.conf import settings

from apps.catalog.models import Event
from .forms import ProfileSettingsForm


def runtime_settings(request):
    favorite_ids = []
    avatar_url = ""
    account_settings_form = None
    account_has_profile = False
    if request.user.is_authenticated:
        account = getattr(request.user, "account", None)
        account_has_profile = account is not None
        account_settings_form = ProfileSettingsForm(auto_id="drawer_%s", initial={
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "newsletter": bool(account and account.newsletter_accepted_at),
        })
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
        "account_settings_form": account_settings_form,
        "account_has_profile": account_has_profile,
    }
