from datetime import timedelta, timezone as datetime_timezone

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Event, PublicationStatus


class EventCalendarTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def setUp(self):
        self.event = Event.objects.first()
        self.event.sessions.all().delete()
        self.start = (timezone.now() + timedelta(days=2)).replace(microsecond=0)
        self.session = self.event.sessions.create(starts_at=self.start, ends_at=self.start + timedelta(hours=1))
        self.url = reverse("catalog:event_calendar", args=[self.event.slug])

    def test_download_contains_the_real_session_and_stable_identifier(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/calendar"))
        self.assertIn("attachment", response["Content-Disposition"])
        text = response.content.replace(b"\r\n ", b"").decode()
        start = self.start.astimezone(datetime_timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.assertIn(f"DTSTART:{start}\r\n", text)
        self.assertIn(f"UID:event-{self.event.pk}-session-{self.session.pk}@testserver\r\n", text)
        self.assertIn("URL:http://testserver" + self.event.get_absolute_url(), text)
        self.assertContains(self.client.get(self.event.get_absolute_url()), self.url)

    def test_period_without_an_exact_session_does_not_create_a_calendar_event(self):
        self.event.sessions.all().delete()
        self.event.available_from = timezone.localdate()
        self.event.available_until = timezone.localdate() + timedelta(days=10)
        self.event.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertNotContains(self.client.get(self.event.get_absolute_url()), self.url)

    def test_calendar_does_not_expose_unpublished_events_or_places(self):
        self.event.status = PublicationStatus.DRAFT
        self.event.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.event.status = PublicationStatus.PUBLISHED
        self.event.save()
        self.event.venue.is_published = False
        self.event.venue.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_text_is_escaped_and_utf8_lines_are_folded_without_splitting_characters(self):
        self.event.title = "Ёжик, мастер-класс; " * 5 + "\nBEGIN:VEVENT"
        self.event.save()
        payload = self.client.get(self.url).content
        for line in payload.split(b"\r\n"):
            self.assertLessEqual(len(line), 75)
            line.decode("utf-8")
        text = payload.replace(b"\r\n ", b"").decode()
        self.assertEqual(text.split("\r\n").count("BEGIN:VEVENT"), 1)
        self.assertIn("Ёжик\\, мастер-класс\\;", text)
        self.assertIn("\\nBEGIN:VEVENT\r\n", text)

    def test_end_time_is_only_exported_when_known(self):
        self.session.ends_at = None
        self.session.save()
        self.event.duration_minutes = None
        self.event.save()
        payload = self.client.get(self.url).content
        self.assertNotIn(b"DTEND:", payload)
        self.assertNotIn(b"DURATION:", payload)
        self.event.duration_minutes = 45
        self.event.save()
        self.assertIn(b"DURATION:PT45M\r\n", self.client.get(self.url).content)
