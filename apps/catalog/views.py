from datetime import datetime, time

from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db.models import Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import ActivityFormat, Category, Event, EventSession


def _base_events():
    upcoming = Prefetch(
        "sessions",
        queryset=EventSession.objects.filter(starts_at__gte=timezone.now()).order_by("starts_at"),
        to_attr="upcoming_sessions",
    )
    return (
        Event.objects.visible()
        .filter(venue__is_published=True)
        .select_related("category", "venue", "organizer", "source")
        .prefetch_related(upcoming)
    )


def _apply_filters(queryset, params):
    query = params.get("q", "").strip()
    if query:
        queryset = queryset.filter(
            Q(title__icontains=query)
            | Q(short_description__icontains=query)
            | Q(venue__name__icontains=query)
            | Q(venue__address__icontains=query)
        )

    category = params.get("category")
    if category:
        queryset = queryset.filter(category__slug=category)

    age = params.get("age")
    if age and age.isdigit():
        queryset = queryset.filter(age_from__lte=int(age), age_to__gte=int(age))

    activity_format = params.get("format")
    if activity_format in ActivityFormat.values:
        queryset = queryset.filter(activity_format__in=(activity_format, ActivityFormat.BOTH))

    max_price = params.get("max_price")
    if max_price and max_price.isdigit():
        queryset = queryset.filter(Q(is_free=True) | Q(price_from__lte=int(max_price)))

    date_value = params.get("date")
    if date_value:
        try:
            selected_date = datetime.strptime(date_value, "%Y-%m-%d").date()
        except ValueError:
            selected_date = None
        if selected_date:
            start = timezone.make_aware(datetime.combine(selected_date, time.min))
            end = timezone.make_aware(datetime.combine(selected_date, time.max))
            queryset = queryset.filter(sessions__starts_at__range=(start, end))

    latitude = params.get("lat")
    longitude = params.get("lng")
    radius = params.get("radius", "5")
    try:
        if latitude and longitude:
            center = Point(float(longitude), float(latitude), srid=4326)
            distance_km = min(max(float(radius), 1), 50)
            queryset = queryset.filter(venue__location__distance_lte=(center, D(km=distance_km)))
    except (TypeError, ValueError):
        pass

    return queryset.distinct()


def event_list(request):
    events = _apply_filters(_base_events(), request.GET).order_by("-is_featured", "title")
    return render(
        request,
        "catalog/event_list.html",
        {
            "events": events,
            "categories": Category.objects.filter(is_active=True).order_by("sort_order", "name"),
            "formats": ActivityFormat.choices,
            "filters": request.GET,
        },
    )


def event_detail(request, slug):
    event = get_object_or_404(_base_events(), slug=slug)
    return render(request, "catalog/event_detail.html", {"event": event})


def event_map(request):
    return render(
        request,
        "catalog/event_map.html",
        {"active_filters": request.GET.urlencode()},
    )


def map_events_api(request):
    events = _apply_filters(_base_events().filter(venue__location__isnull=False), request.GET).order_by("title")[:500]
    payload = []
    for event in events:
        point = event.venue.location
        payload.append(
            {
                "id": event.pk,
                "title": event.title,
                "category": event.category.name,
                "age": f"{event.age_from}–{event.age_to} лет",
                "price": event.display_price,
                "address": event.venue.address,
                "lat": point.y,
                "lng": point.x,
                "url": event.get_absolute_url(),
                "cover": event.cover_url,
            }
        )
    return JsonResponse({"count": len(payload), "results": payload})
