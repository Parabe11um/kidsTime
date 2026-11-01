from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.models import Account
from apps.catalog.models import Category
from apps.catalog.views import _base_events
from .forms import ProfileAvatarForm, ProfileSettingsForm


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
    week_start = today - timedelta(days=today.weekday())
    for offset in range(21):
        day = week_start + timedelta(days=offset)
        days.append(
            {
                "date": day.isoformat(),
                "weekday": WEEKDAYS[day.weekday()],
                "day": day.day,
                "month": MONTHS[day.month],
                "is_today": day == today,
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
        "feed_top_events": events[:10],
        "feed_new_events": _base_events().order_by("-created_at", "pk")[:10],
        "feed_free_events": _base_events().filter(is_free=True).order_by("-is_featured", "title")[:10],
    }
    return render(request, "core/home.html", context)


@require_http_methods(["GET", "POST"])
def profile(request):
    if not request.user.is_authenticated:
        if request.method == "POST":
            return redirect("accounts:login")
        return render(request, "core/profile.html", {"today": timezone.localdate()})
    account = getattr(request.user, "account", None)
    form = ProfileSettingsForm(request.POST if request.method == "POST" else None, initial={
        "first_name": request.user.first_name,
        "last_name": request.user.last_name,
        "newsletter": bool(account and account.newsletter_accepted_at),
    })
    if request.method == "POST" and form.is_valid():
        request.user.first_name = form.cleaned_data["first_name"]
        request.user.last_name = form.cleaned_data["last_name"]
        request.user.save(update_fields=["first_name", "last_name"])
        if account:
            if not form.cleaned_data["newsletter"]:
                account.newsletter_accepted_at = None
            elif not account.newsletter_accepted_at:
                account.newsletter_accepted_at = timezone.now()
            account.save(update_fields=["newsletter_accepted_at"])
        messages.success(request, "Настройки сохранены")
        return_to = request.POST.get("next", "")
        if url_has_allowed_host_and_scheme(return_to, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            return redirect(return_to)
        return redirect("core:profile")
    return render(request, "core/profile.html", {"today": timezone.localdate(), "settings_form": form, "profile_account": account})


@login_required
@require_POST
def profile_avatar(request):
    account = get_object_or_404(Account, user=request.user)
    form = ProfileAvatarForm(request.POST, request.FILES)
    if form.is_valid():
        account.avatar = form.cleaned_data["avatar"]
        account.save(update_fields=["avatar"])
        messages.success(request, "Фото профиля обновлено")
    else:
        for error in form.errors.get("avatar", []):
            messages.error(request, error)
    return redirect("core:profile")


def privacy(request):
    response = render(request, "core/privacy.html", {
        "test_registration_enabled": settings.TEST_REGISTRATION_ENABLED,
    })
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


def health(request):
    return JsonResponse({"status": "ok", "service": "kidstime"})


def robots_txt(request):
    rule = "Disallow: /" if settings.ROBOTS_NOINDEX else "Allow: /"
    return HttpResponse(
        f"User-agent: *\n{rule}\n",
        content_type="text/plain; charset=utf-8",
    )
