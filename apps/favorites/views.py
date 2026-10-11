import json

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.catalog.views import _base_events, _event_ids_from_query
from apps.catalog.models import Event

from .models import Favorite


def favorite_list(request):
    return render(request, "catalog/favorites.html")


def favorite_cards(request):
    if request.user.is_authenticated:
        event_ids = list(request.user.favorites.values_list("event_id", flat=True)[:100])
    else:
        event_ids = _event_ids_from_query(request.GET.get("ids", ""), limit=100)
    events_by_id = {event.pk: event for event in _base_events().filter(pk__in=event_ids)}
    events = [events_by_id[event_id] for event_id in event_ids if event_id in events_by_id]
    return render(request, "catalog/favorite_cards.html", {"events": events})


@login_required
@require_POST
@transaction.atomic
def toggle_favorite(request, event_id):
    get_user_model().objects.select_for_update().get(pk=request.user.pk)
    event = get_object_or_404(Event.objects.visible(), pk=event_id)
    if not Favorite.objects.filter(user=request.user, event=event).exists() and request.user.favorites.count() >= 100:
        return JsonResponse({"error": "Можно сохранить до 100 событий."}, status=400)
    favorite, created = Favorite.objects.get_or_create(user=request.user, event=event)
    if not created:
        favorite.delete()
    return JsonResponse({"favorite": created})


def _favorite_ids(user):
    return list(user.favorites.filter(event__in=Event.objects.visible()).values_list("event_id", flat=True)[:100])


@login_required
@require_POST
@transaction.atomic
def set_favorite(request, event_id):
    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Некорректный запрос."}, status=400)
    if not isinstance(payload, dict) or type(payload.get("favorite")) is not bool:
        return JsonResponse({"error": "Укажите действие с избранным."}, status=400)
    get_user_model().objects.select_for_update().get(pk=request.user.pk)
    event = get_object_or_404(Event.objects.visible(), pk=event_id)
    if payload["favorite"]:
        if not Favorite.objects.filter(user=request.user, event=event).exists() and request.user.favorites.count() >= 100:
            return JsonResponse({"error": "Можно сохранить до 100 событий."}, status=400)
        Favorite.objects.get_or_create(user=request.user, event=event)
    else:
        Favorite.objects.filter(user=request.user, event=event).delete()
    return JsonResponse({"ids": _favorite_ids(request.user)})


@login_required
@require_POST
@transaction.atomic
def merge_favorites(request):
    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Некорректный запрос."}, status=400)
    if not isinstance(payload, dict) or not isinstance(payload.get("ids"), list) or len(payload["ids"]) > 100:
        return JsonResponse({"error": "Ожидается список до 100 событий."}, status=400)
    ids = _event_ids_from_query(",".join(str(value) for value in payload["ids"]), limit=100)
    get_user_model().objects.select_for_update().get(pk=request.user.pk)
    existing = set(request.user.favorites.values_list("event_id", flat=True))
    capacity = max(0, 100 - len(existing))
    new_ids = list(Event.objects.visible().filter(pk__in=ids).exclude(pk__in=existing).values_list("pk", flat=True))[:capacity]
    Favorite.objects.bulk_create([Favorite(user=request.user, event_id=pk) for pk in new_ids], ignore_conflicts=True)
    return JsonResponse({"ids": _favorite_ids(request.user)})
