from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.catalog.views import _base_events
from apps.catalog.models import Event

from .models import Favorite


def favorite_list(request):
    return render(request, "catalog/favorites.html")


def favorite_cards(request):
    raw_ids = request.GET.get("ids", "")
    event_ids = [int(value) for value in raw_ids.split(",") if value.strip().isdigit()][:100]
    events_by_id = {event.pk: event for event in _base_events().filter(pk__in=event_ids)}
    events = [events_by_id[event_id] for event_id in event_ids if event_id in events_by_id]
    return render(request, "catalog/favorite_cards.html", {"events": events})


@login_required
@require_POST
def toggle_favorite(request, event_id):
    event = get_object_or_404(Event.objects.visible(), pk=event_id)
    favorite, created = Favorite.objects.get_or_create(user=request.user, event=event)
    if not created:
        favorite.delete()
    return JsonResponse({"favorite": created})
