from datetime import timedelta

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone

from apps.catalog.models import Category
from apps.catalog.views import _base_events


WEEKDAYS = ("пн", "вт", "ср", "чт", "пт", "сб", "вс")
MONTHS = (
    "",
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
)


def home(request):
    today = timezone.localdate()
    events = list(
        _base_events().order_by("-is_featured", "-is_recommended", "title")[:24]
    )

    days = []
    for offset in range(21):
        day = today + timedelta(days=offset)
        days.append(
            {
                "date": day.isoformat(),
                "weekday": WEEKDAYS[day.weekday()],
                "day": day.day,
                "month": MONTHS[day.month],
                "is_today": offset == 0,
                "is_weekend": day.weekday() >= 5,
            }
        )

    context = {
        "days": days,
        "categories": Category.objects.filter(is_active=True).order_by("sort_order", "name"),
        "spotlight_events": events[:5],
        "story_events": [event for event in events if event.display_cover_url][:6],
        "nearby_events": events[:6],
        "recommended_events": [event for event in events if event.is_recommended][:6] or events[:6],
        "popular_events": [event for event in events if event.is_featured][:6] or events[:6],
        "feed_events": events[:10],
        "event_count": _base_events().count(),
    }
    return render(request, "core/home.html", context)


def profile(request):
    return render(request, "core/profile.html", {"today": timezone.localdate()})


def health(request):
    return JsonResponse({"status": "ok", "service": "kidstime"})


def robots_txt(request):
    rule = "Disallow: /" if settings.ROBOTS_NOINDEX else "Allow: /"
    return HttpResponse(
        f"User-agent: *\n{rule}\n",
        content_type="text/plain; charset=utf-8",
    )
