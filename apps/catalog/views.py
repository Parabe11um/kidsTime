from datetime import datetime, time
from math import isfinite

from django.conf import settings
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_safe

from .models import ActivityFormat, Category, Event, EventImage, EventSession
from .services.calendar import build_event_calendar

WALK_POINT_LIMIT = 9
MOSCOW_CENTER = Point(37.6176, 55.7558, srid=4326)
NEARBY_RADIUS_KM = 5


def _base_events():
    upcoming = Prefetch(
        "sessions",
        queryset=EventSession.objects.filter(starts_at__gte=timezone.now()).order_by("starts_at"),
        to_attr="upcoming_sessions",
    )
    images = Prefetch(
        "images",
        queryset=EventImage.objects.order_by("-is_cover", "sort_order", "pk"),
        to_attr="prefetched_images",
    )
    return (
        Event.objects.visible()
        .filter(venue__is_published=True)
        .select_related("category", "venue", "organizer", "source")
        .prefetch_related(upcoming, images)
    )


def _location_filter(params):
    try:
        lat = float(params.get("lat"))
        lng = float(params.get("lng"))
        radius = float(params.get("radius") or NEARBY_RADIUS_KM)
    except (TypeError, ValueError):
        return None, NEARBY_RADIUS_KM
    if -90 <= lat <= 90 and -180 <= lng <= 180 and isfinite(radius):
        return Point(lng, lat, srid=4326), min(max(radius, 1), 50)
    return None, NEARBY_RADIUS_KM


def nearby_events(queryset, center, radius=NEARBY_RADIUS_KM):
    return queryset.filter(venue__location__distance_lte=(center, D(km=radius))).order_by(
        Distance("venue__location", center), "title", "pk",
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
    age_groups = {"0-3": (0, 3), "4-7": (4, 7), "8-11": (8, 11), "12+": (12, 18)}
    if params.get("age_group") in age_groups:
        lower, upper = age_groups[params["age_group"]]
        queryset = queryset.filter(age_from__lte=upper, age_to__gte=lower)
    elif age and age.isascii() and age.isdigit() and len(age) <= 2:
        queryset = queryset.filter(age_from__lte=int(age), age_to__gte=int(age))

    activity_format = params.get("format")
    if activity_format in ActivityFormat.values:
        queryset = queryset.filter(activity_format__in=(activity_format, ActivityFormat.BOTH))

    max_price = params.get("max_price")
    if max_price and max_price.isascii() and max_price.isdigit() and len(max_price) <= 8:
        queryset = queryset.filter(Q(is_free=True) | Q(price_from__lte=int(max_price)))

    if params.get("free") == "1":
        queryset = queryset.filter(is_free=True)
    if params.get("accessible") == "1":
        queryset = queryset.filter(venue__accessible=True)
    if params.get("stroller") == "1":
        queryset = queryset.filter(venue__stroller_access=True)
    if params.get("parking") == "1":
        queryset = queryset.exclude(venue__parking_notes="")
    if params.get("metro") == "1":
        queryset = queryset.exclude(venue__metro="")
    if params.get("children_room") == "1":
        queryset = queryset.filter(venue__has_children_room=True)
    if params.get("cafe") == "1":
        queryset = queryset.filter(venue__has_cafe=True)
    if params.get("pushkin_card") == "1":
        queryset = queryset.filter(accepts_pushkin_card=True)
    if params.get("collection") == "recommended":
        queryset = queryset.filter(is_recommended=True)
    elif params.get("collection") == "popular":
        queryset = queryset.filter(is_featured=True)

    def parse_date(value):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None

    selected_date = parse_date(params.get("date"))
    first_day = selected_date or parse_date(params.get("date_from"))
    last_day = selected_date or parse_date(params.get("date_until"))
    session_dates, period_dates = Q(), Q(sessions__isnull=True)
    if first_day:
        session_dates &= Q(sessions__starts_at__gte=timezone.make_aware(datetime.combine(first_day, time.min)))
        period_dates &= Q(available_until__gte=first_day)
    if last_day:
        session_dates &= Q(sessions__starts_at__lte=timezone.make_aware(datetime.combine(last_day, time.max)))
        period_dates &= Q(available_from__lte=last_day)

    clock_filters = Q()
    has_clock = False
    for key, lookup in (("time_from", "gte"), ("time_until", "lte")):
        try:
            clock = datetime.strptime(params.get(key, ""), "%H:%M").time()
        except (ValueError, TypeError):
            continue
        clock_filters &= Q(**{f"sessions__starts_at__time__{lookup}": clock})
        has_clock = True
    if has_clock:
        # Date and clock must match the same real session, never two different rows.
        queryset = queryset.filter(session_dates & clock_filters & Q(sessions__starts_at__gte=timezone.now()))
    elif first_day or last_day:
        queryset = queryset.filter(session_dates | period_dates)

    center, radius = _location_filter(params)
    if params.get("collection") == "nearby":
        center = center if center is not None else MOSCOW_CENTER
        radius = NEARBY_RADIUS_KM
    if center is not None:
        queryset = queryset.filter(venue__location__distance_lte=(center, D(km=radius)))

    return queryset.distinct()


def _pagination(request, queryset, page_size):
    page = Paginator(queryset, page_size).get_page(request.GET.get("page"))
    query_params = request.GET.copy()
    query_params.pop("page", None)
    return {
        "events": page.object_list,
        "page_obj": page,
        "page_numbers": page.paginator.get_elided_page_range(page.number, on_each_side=2, on_ends=1),
        "pagination_query": query_params.urlencode(),
    }


def event_list(request):
    order = ("-created_at", "title") if request.GET.get("collection") == "new" else ("-is_featured", "title")
    queryset = _apply_filters(_base_events(), request.GET).order_by(*order, "pk")
    pagination = _pagination(request, queryset, 12)
    count = pagination["page_obj"].paginator.count
    last_digit = count % 10
    if 11 <= count % 100 <= 14:
        count_word = "событий"
    elif last_digit == 1:
        count_word = "событие"
    elif 2 <= last_digit <= 4:
        count_word = "события"
    else:
        count_word = "событий"
    has_filters = any(value for key, value in request.GET.items() if key not in ("filters", "page"))
    return render(
        request,
        "catalog/event_list.html",
        {
            **pagination,
            "result_count": count,
            "result_count_word": count_word,
            "categories": Category.objects.filter(is_active=True).order_by("sort_order", "name"),
            "formats": ActivityFormat.choices,
            "filters": request.GET,
            "has_filters": has_filters,
            "spotlight_event": pagination["events"].first() if not has_filters else None,
        },
    )


@require_safe
def event_collection(request, collection):
    events = _base_events()
    location = None
    auto_locate = False
    map_query = {"collection": collection}
    if collection == "nearby":
        title = "Рядом с вами"
        description = "Интересные места и постоянные площадки поблизости"
        coordinates, _ = _location_filter(request.GET)
        center = coordinates if coordinates is not None else MOSCOW_CENTER
        location = "Ваше местоположение" if coordinates is not None else "Москва, центр"
        events = nearby_events(events, center)
        if coordinates is not None:
            map_query.update(lat=coordinates.y, lng=coordinates.x)
        elif "page" not in request.GET:
            auto_locate = getattr(getattr(request.user, "account", None), "use_geolocation", False)
    else:
        title = "Популярное"
        description = "События, на которые стоит обратить внимание"
        events = events.filter(is_featured=True).order_by("title", "pk")
        map_query["from"] = "collection"
    return render(
        request,
        "catalog/event_collection.html",
        {
            **_pagination(request, events, 9),
            "title": title,
            "description": description,
            "location": location,
            "auto_locate": auto_locate,
            "map_url": reverse("catalog:event_map", query=map_query),
        },
    )


def event_detail(request, slug):
    event = get_object_or_404(_base_events(), slug=slug)
    gallery = [{"url": image.image.url, "alt": image.alt_text} for image in event.prefetched_images]
    if not gallery and event.display_cover_url:
        gallery = [{"url": event.display_cover_url, "alt": event.title}]
    return render(request, "catalog/event_detail.html", {
        "event": event,
        "gallery": gallery,
        "venue_events": _base_events().filter(venue=event.venue).exclude(pk=event.pk)[:6],
        "related_events": _base_events().filter(category=event.category).exclude(pk=event.pk)[:6],
    })


def event_map(request):
    center, _ = _location_filter(request.GET)
    collection = request.GET.get("collection")
    if collection == "nearby":
        if center is None:
            center = MOSCOW_CENTER
        back_url = reverse("catalog:nearby", query={key: request.GET[key] for key in ("lat", "lng") if key in request.GET})
    elif collection == "popular" and request.GET.get("from") == "collection":
        back_url = reverse("catalog:popular")
    else:
        back_url = reverse("catalog:event_list", query=request.GET)
    return render(
        request,
        "catalog/event_map.html",
        {"active_filters": request.GET.urlencode(), "back_url": back_url, "center": center},
    )


@require_safe
def event_calendar(request, slug):
    event = get_object_or_404(_base_events(), slug=slug)
    session = event.next_session
    if session is None:
        raise Http404("Нет предстоящего сеанса с точным временем.")
    response = HttpResponse(
        build_event_calendar(event, session, request.build_absolute_uri(event.get_absolute_url()), timezone.now()),
        content_type="text/calendar; charset=utf-8",
    )
    response["Content-Disposition"] = f'attachment; filename="kidstime-event-{event.pk}.ics"'
    response["Cache-Control"] = "no-store"
    return response


def walk_builder(request):
    return render(
        request,
        "catalog/walk_builder.html",
        {
            "walk_point_limit": WALK_POINT_LIMIT,
            "walk_geocoder_enabled": bool(settings.YANDEX_GEOCODER_API_KEY),
        },
    )


@require_safe
def saved_walks(request):
    return render(request, "catalog/saved_walks.html", {"walk_point_limit": WALK_POINT_LIMIT})


def _event_ids_from_query(raw_ids, *, limit):
    event_ids = []
    for raw_value in raw_ids.split(","):
        value = raw_value.strip()
        if not value.isascii() or not value.isdigit() or len(value) > 19:
            continue
        event_id = int(value)
        if not 0 < event_id <= 2**63 - 1:
            continue
        if event_id not in event_ids:
            event_ids.append(event_id)
        if len(event_ids) == limit:
            break
    return event_ids


def walk_events_api(request):
    event_ids = _event_ids_from_query(
        request.GET.get("ids", ""),
        limit=WALK_POINT_LIMIT,
    )
    events_by_id = {
        event.pk: event
        for event in _base_events().filter(
            pk__in=event_ids,
            venue__location__isnull=False,
        )
    }
    events = [
        events_by_id[event_id]
        for event_id in event_ids
        if event_id in events_by_id
    ]
    payload = []
    for event in events:
        point = event.venue.location
        payload.append(
            {
                "id": event.pk,
                "title": event.title,
                "venue": event.venue.name,
                "address": event.venue.address,
                "description": event.short_description,
                "lat": point.y,
                "lng": point.x,
                "url": event.get_absolute_url(),
                "cover": event.display_cover_url,
                "age": f"{event.age_from}+",
                "price": event.display_price,
                "date": (
                    date_format(timezone.localtime(event.next_session.starts_at), "j E")
                    if event.next_session else
                    f"до {date_format(event.available_until, 'j E')}" if event.available_until else "Уточняется"
                ),
            }
        )
    return JsonResponse(
        {
            "count": len(payload),
            "limit": WALK_POINT_LIMIT,
            "results": payload,
        }
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
                "cover": event.display_cover_url,
            }
        )
    return JsonResponse({"count": len(payload), "results": payload})
