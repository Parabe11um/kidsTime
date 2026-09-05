import io
import json
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from .models import (
    Category,
    Event,
    EventImage,
    ImportedEvent,
    ImportedEventStatus,
    ImportRun,
    PublicationStatus,
    Source,
    Venue,
)
from .services.imports import promote_imported_event


class PublicPagesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command

        call_command("seed_demo", verbosity=0)

    def test_home_page_uses_catalog_data(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Куда пойдём")
        self.assertContains(response, Event.objects.first().title)

    def test_catalog_filters_by_age(self):
        response = self.client.get(reverse("catalog:event_list"), {"age": 4})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(all(event.age_from <= 4 <= event.age_to for event in response.context["events"]))

    def test_map_api_returns_coordinates(self):
        response = self.client.get(reverse("catalog:map_events_api"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreater(payload["count"], 0)
        self.assertIn("lat", payload["results"][0])

    def test_map_page_allows_origin_referrer_for_yandex_maps(self):
        response = self.client.get(reverse("catalog:event_map"))

        self.assertEqual(
            response.headers["Referrer-Policy"],
            "strict-origin-when-cross-origin",
        )

    def test_uploaded_cover_has_priority_over_legacy_url(self):
        event = Event.objects.first()
        EventImage.objects.create(event=event, image="events/test-cover.jpg", is_cover=True)

        self.assertEqual(event.display_cover_url, "/media/events/test-cover.jpg")


class VenueAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)
        cls.user = get_user_model().objects.create_superuser(
            username="editor",
            email="editor@example.com",
            password="test-password",
        )

    @override_settings(YANDEX_MAPS_API_KEY="test-key")
    def test_change_page_contains_coordinate_picker(self):
        self.client.force_login(self.user)
        venue = Venue.objects.first()

        response = self.client.get(reverse("admin:catalog_venue_change", args=(venue.pk,)))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-venue-map')
        self.assertContains(response, 'data-map-enabled="true"')
        self.assertContains(response, "api-maps.yandex.ru/v3/")


class StageEventsCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.source = Source.objects.create(name="Тестовая лента", parser_code="test-feed")
        Category.objects.create(name="Музеи", slug="museums")

    def test_dry_run_does_not_change_database(self):
        path = self._write_payload()
        output = io.StringIO()

        call_command("stage_events", path, source="test-feed", dry_run=True, stdout=output)

        self.assertEqual(ImportedEvent.objects.count(), 0)
        self.assertEqual(ImportRun.objects.count(), 0)
        self.assertIn("MODE=CHECK", output.getvalue())
        self.assertIn("rolled_back=yes", output.getvalue())

    def test_apply_stages_event_without_publishing(self):
        path = self._write_payload()
        output = io.StringIO()

        call_command("stage_events", path, source=str(self.source.pk), stdout=output)

        imported = ImportedEvent.objects.get()
        self.assertEqual(imported.title, "Научная ёлка")
        self.assertIsNone(imported.event)
        self.assertEqual(ImportRun.objects.get().staged_count, 1)
        self.assertIn("MODE=APPLY", output.getvalue())
        self.assertIn("rolled_back=no", output.getvalue())

    def test_reviewed_import_can_create_prefilled_draft(self):
        path = self._write_payload()
        call_command("stage_events", path, source="test-feed", stdout=io.StringIO())

        imported = ImportedEvent.objects.get()
        event = promote_imported_event(imported)

        imported.refresh_from_db()
        self.assertEqual(imported.status, ImportedEventStatus.IMPORTED)
        self.assertEqual(event.status, PublicationStatus.DRAFT)
        self.assertEqual(event.venue.name, "Музей науки")
        self.assertFalse(event.venue.is_published)
        self.assertEqual(event.sessions.count(), 1)

    def _write_payload(self):
        payload = [
            {
                "external_id": "event-42",
                "title": "Научная ёлка",
                "source_url": "https://example.com/events/42",
                "venue_name": "Музей науки",
                "address": "Москва, Примерная улица, 1",
                "category": "museums",
                "organizer": "Музей науки",
                "age_from": 6,
                "age_to": 12,
                "sessions": [{"starts_at": "2026-12-20T12:00:00+03:00"}],
            }
        ]
        temporary = tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8", delete=False)
        with temporary:
            json.dump(payload, temporary, ensure_ascii=False)
        self.addCleanup(Path(temporary.name).unlink, missing_ok=True)
        return temporary.name
