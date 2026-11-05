import json

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.accounts.limits import rate_limited
from .models import Event
from .services.routing import RoutingUnavailable, geocode, route_legs, valid_coordinate
from .views import WALK_POINT_LIMIT


def _error(code, status):
    return JsonResponse({"error": code}, status=status)


def _body(request):
    if request.content_type != "application/json":
        raise ValueError
    raw = request.body
    if len(raw) > 4096:
        raise ValueError
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError
    return payload


def _point(value):
    if not isinstance(value, dict) or not valid_coordinate(value.get("lat"), 90) or not valid_coordinate(value.get("lng"), 180):
        raise ValueError
    return {"lat": value["lat"], "lng": value["lng"]}


def _limited(request, action):
    # Existing shared DB counters also work across production Gunicorn workers.
    if rate_limited(request, action):
        response = _error("rate_limited", 429)
        response["Retry-After"] = "3600"
        return response
    return None


@never_cache
@require_POST
def walk_route_times(request):
    if not settings.YANDEX_ROUTER_API_KEY:
        return _error("routing_unavailable", 503)
    try:
        payload = _body(request)
        raw_ids = payload.get("ids")
        if not isinstance(raw_ids, list) or not 1 <= len(raw_ids) <= WALK_POINT_LIMIT:
            raise ValueError
        ids = []
        for value in raw_ids:
            if isinstance(value, bool) or not isinstance(value, (int, str)):
                raise ValueError
            text = str(value)
            if not text.isascii() or not text.isdigit() or len(text) > 19 or not 0 < int(text) <= 2**63 - 1 or int(text) in ids:
                raise ValueError
            ids.append(int(text))
        mode = payload.get("mode", "walking")
        if mode not in ("walking", "driving", "transit"):
            raise ValueError
        origin = _point(payload["origin"]) if payload.get("origin") is not None else None
        if len(ids) + bool(origin) < 2:
            raise ValueError
    except (ValueError, TypeError, UnicodeError, RecursionError):
        return _error("invalid_request", 400)
    points_by_id = dict(Event.objects.visible().filter(
        pk__in=ids, venue__is_published=True, venue__location__isnull=False,
    ).values_list("pk", "venue__location"))
    if len(points_by_id) != len(ids):
        return _error("route_changed", 409)
    limited = _limited(request, "walk-routing")
    if limited is not None:
        return limited
    points = ([origin] if origin else []) + [
        {"lat": points_by_id[pk].y, "lng": points_by_id[pk].x} for pk in ids
    ]
    labels = (["origin"] if origin else []) + [str(pk) for pk in ids]
    try:
        legs = route_legs(points, mode, settings.YANDEX_ROUTER_API_KEY)
    except RoutingUnavailable:
        return _error("routing_unavailable", 503)
    return JsonResponse({
        "mode": mode,
        "calculated_at": timezone.now().isoformat(),
        "legs": [dict(leg, from_id=labels[index], to_id=labels[index + 1]) for index, leg in enumerate(legs)],
    })


@never_cache
@require_POST
def walk_geocode(request):
    if not settings.YANDEX_GEOCODER_API_KEY:
        return _error("geocoding_unavailable", 503)
    try:
        payload = _body(request)
        reverse = payload.get("point") is not None
        if reverse:
            point = _point(payload["point"])
            query = f'{point["lng"]:.6f},{point["lat"]:.6f}'
        else:
            query = payload.get("query")
            if not isinstance(query, str) or not 2 <= len(query.strip()) <= 200:
                raise ValueError
            query = query.strip()
    except (ValueError, TypeError, UnicodeError, RecursionError):
        return _error("invalid_request", 400)
    limited = _limited(request, "walk-geocoding")
    if limited is not None:
        return limited
    try:
        results = geocode(query, settings.YANDEX_GEOCODER_API_KEY, reverse=reverse)
    except RoutingUnavailable:
        return _error("geocoding_unavailable", 503)
    return JsonResponse({"results": results})
