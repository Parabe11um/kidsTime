from datetime import timedelta

from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from apps.catalog.models import Category, Event, EventSession


WEEKDAYS = ("пн", "вт", "ср", "чт", "пт", "сб", "вс")
MONTHS = (
    "",
    "янв",
    "фев",
    "мар",
    "апр",
    "мая",
    "июн",
    "июл",
    "авг",
    "сен",
    "окт",
    "ноя",
    "дек",
)


def home(request):
    now = timezone.now()
    today = timezone.localdate()
    upcoming = Prefetch(
        "sessions",
        queryset=EventSession.objects.filter(starts_at__gte=now).order_by("starts_at"),
        to_attr="upcoming_sessions",
    )
    events = list(
        Event.objects.visible()
        .select_related("category", "venue", "organizer")
        .prefetch_related(upcoming)
        .order_by("-is_featured", "-is_recommended", "title")[:18]
    )

    days = []
    for offset in range(7):
        day = today + timedelta(days=offset)
        days.append(
            {
                "date": day.isoformat(),
                "weekday": WEEKDAYS[day.weekday()],
                "day": day.day,
                "month": MONTHS[day.month],
                "is_today": offset == 0,
            }
        )

    context = {
        "days": days,
        "categories": Category.objects.filter(is_active=True).order_by("sort_order", "name")[:8],
        "nearby_events": events[:6],
        "recommended_events": [event for event in events if event.is_recommended][:6] or events[6:12],
        "popular_events": [event for event in events if event.is_featured][:6] or events[12:18],
    }
    return render(request, "core/home.html", context)


def health(request):
    return JsonResponse({"status": "ok", "service": "kidstime"})
