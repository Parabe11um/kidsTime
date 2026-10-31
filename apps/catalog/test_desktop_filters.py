from datetime import datetime, time, timedelta

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Event, EventSession


class DesktopSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def test_range_includes_overlapping_period_without_inventing_sessions(self):
        event = Event.objects.first()
        event.sessions.all().delete()
        day = timezone.localdate() + timedelta(days=5)
        event.available_from = day
        event.available_until = day + timedelta(days=4)
        event.save(update_fields=["available_from", "available_until"])
        url = reverse("catalog:event_list")
        response = self.client.get(url, {"date_from": (day + timedelta(days=2)).isoformat(), "date_until": (day + timedelta(days=6)).isoformat()})
        self.assertIn(event, response.context["events"])
        response = self.client.get(url, {"date_from": (day + timedelta(days=5)).isoformat()})
        self.assertNotIn(event, response.context["events"])
        response = self.client.get(url, {"date_from": day.isoformat(), "time_from": "12:00"})
        self.assertNotIn(event, response.context["events"])
        self.assertEqual(event.sessions.count(), 0)

    def test_date_and_time_must_belong_to_the_same_future_session(self):
        event = Event.objects.first()
        event.sessions.all().delete()
        day = timezone.localdate() + timedelta(days=10)
        for offset, hour in ((0, 9), (1, 18)):
            EventSession.objects.create(event=event, starts_at=timezone.make_aware(datetime.combine(day + timedelta(days=offset), time(hour))))
        params = {"date_from": day.isoformat(), "date_until": day.isoformat(), "time_from": "17:00", "time_until": "19:00"}
        self.assertNotIn(event, self.client.get(reverse("catalog:event_list"), params).context["events"])
        params["date_until"] = (day + timedelta(days=1)).isoformat()
        self.assertIn(event, self.client.get(reverse("catalog:event_list"), params).context["events"])

    def test_pagination_retains_filters_and_does_not_repeat_results(self):
        original = Event.objects.first()
        for index in range(25):
            Event.objects.create(title=f"Пагинация {index:02}", slug=f"pagination-{index}", category=original.category, venue=original.venue, organizer=original.organizer, source=original.source, status=original.status)
        first = self.client.get(reverse("catalog:event_list"), {"q": "Пагинация"})
        second = self.client.get(reverse("catalog:event_list"), {"q": "Пагинация", "page": 2})
        self.assertEqual(first.context["result_count"], 25)
        self.assertEqual(len(first.context["events"]), 12)
        self.assertEqual(len(second.context["events"]), 12)
        self.assertFalse({e.pk for e in first.context["events"]} & {e.pk for e in second.context["events"]})
        self.assertContains(first, "page=2")
        self.assertIn("q=", first.context["pagination_query"])

    def test_invalid_filter_values_and_page_are_safe(self):
        response = self.client.get(reverse("catalog:event_list"), {"date_from": "invalid", "date_until": "2026-99-99", "time_from": "99:99", "page": "bad"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].number, 1)
