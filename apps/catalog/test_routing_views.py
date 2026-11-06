import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.gis.geos import Point
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Category, Event, Organizer, PublicationStatus, Source, Venue
from .services.routing import RoutingUnavailable


@override_settings(YANDEX_ROUTER_API_KEY="private-routing-key", YANDEX_GEOCODER_API_KEY="private-geocoder-key")
class WalkRoutingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        category = Category.objects.create(name="Музеи", slug="museums")
        organizer = Organizer.objects.create(name="Музей")
        source = Source.objects.create(name="Проверенный источник")
        cls.events = []
        for i, (lng, lat) in enumerate(((37.6, 55.7), (37.65, 55.75))):
            venue = Venue.objects.create(name=f"Место {i}", slug=f"place-{i}", address=f"Москва, адрес {i}", location=Point(lng, lat, srid=4326))
            cls.events.append(Event.objects.create(title=f"Событие {i}", slug=f"event-{i}", category=category, organizer=organizer, source=source, venue=venue, status=PublicationStatus.PUBLISHED))

    def request(self, body=None, client=None):
        if body is None:
            body = {"ids": [event.pk for event in self.events], "mode": "walking"}
        return (client or self.client).post(reverse("catalog:walk_route_times"), data=json.dumps(body), content_type="application/json")

    def test_page_keeps_origin_controls_without_travel_time_ui_or_private_keys(self):
        response = self.client.get(reverse("catalog:walk_builder"))
        self.assertContains(response, 'data-origin-search')
        self.assertContains(response, 'data-walk-locate')
        self.assertContains(response, 'data-walk-origin-open')
        for removed in (
            'data-times-endpoint', 'data-routing-enabled',
            'data-walk-time-note', 'data-walk-times-retry',
            'Уточнить время', 'Обновить время',
        ):
            with self.subTest(removed=removed):
                self.assertNotContains(response, removed)
        self.assertNotContains(response, "private-routing-key")
        self.assertNotContains(response, "private-geocoder-key")

    @patch("apps.catalog.routing_views.route_legs", return_value=[{"seconds": 2700, "meters": 3000}, {"seconds": 600, "meters": 700}])
    def test_origin_and_selected_order_are_kept_and_response_is_private(self, calculate):
        a, b = self.events
        response = self.request({"ids": [b.pk, a.pk], "origin": {"lat": 55.72, "lng": 37.62}, "mode": "transit"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([(leg["from_id"], leg["to_id"]) for leg in response.json()["legs"]], [("origin", str(b.pk)), (str(b.pk), str(a.pk))])
        self.assertEqual(calculate.call_args.args[:2], ([{"lat": 55.72, "lng": 37.62}, {"lat": 55.75, "lng": 37.65}, {"lat": 55.7, "lng": 37.6}], "transit"))
        self.assertIn("no-store", response["Cache-Control"])
        self.assertNotIn("private-routing-key", response.content.decode())

    @patch("apps.catalog.routing_views.route_legs")
    def test_invalid_requests_never_call_the_provider(self, calculate):
        ids = [event.pk for event in self.events]
        for body in (
            [], {"ids": ids, "mode": {}}, {"ids": [True, ids[0]]}, {"ids": [ids[0], ids[0]]},
            {"ids": [ids[0]]}, {"ids": ids * 5}, {"ids": ["9" * 100]},
            {"ids": ids, "origin": {"lat": True, "lng": 37}},
            {"ids": ids, "origin": {"lat": float("nan"), "lng": 37}},
            {"ids": ids, "origin": {"lat": 91, "lng": 37}},
        ):
            with self.subTest(body=body):
                self.assertEqual(self.request(body).status_code, 400)
        self.assertEqual(self.client.post(reverse("catalog:walk_route_times"), data="{bad", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.get(reverse("catalog:walk_route_times")).status_code, 405)
        calculate.assert_not_called()

    @patch("apps.catalog.routing_views.route_legs")
    def test_hidden_expired_or_unlocated_places_cannot_be_routed(self, calculate):
        event = self.events[0]
        event.status = PublicationStatus.DRAFT
        event.save(update_fields=["status"])
        self.assertEqual(self.request().status_code, 409)
        event.status = PublicationStatus.PUBLISHED
        event.available_until = timezone.localdate() - timedelta(days=1)
        event.save(update_fields=["status", "available_until"])
        self.assertEqual(self.request().status_code, 409)
        event.available_until = None
        event.save(update_fields=["available_until"])
        event.venue.is_published = False
        event.venue.save(update_fields=["is_published"])
        self.assertEqual(self.request().status_code, 409)
        event.venue.is_published = True
        event.venue.location = None
        event.venue.save(update_fields=["is_published", "location"])
        self.assertEqual(self.request().status_code, 409)
        calculate.assert_not_called()

    @patch("apps.catalog.routing_views.route_legs", return_value=[{"seconds": 10, "meters": 12}])
    def test_csrf_is_required_for_anonymous_calculations(self, calculate):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(self.request(client=client).status_code, 403)
        calculate.assert_not_called()
        client.get(reverse("catalog:walk_builder"))
        response = client.post(reverse("catalog:walk_route_times"), data=json.dumps({"ids": [event.pk for event in self.events]}), content_type="application/json", HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
        self.assertEqual(response.status_code, 200)

    @patch("apps.catalog.routing_views.route_legs", return_value=[{"seconds": 10, "meters": 12}])
    def test_shared_rate_limit_stops_paid_provider_calls(self, calculate):
        for _ in range(20):
            self.assertEqual(self.request().status_code, 200)
        response = self.request()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], "3600")
        self.assertEqual(calculate.call_count, 20)

    @override_settings(YANDEX_ROUTER_API_KEY="", YANDEX_GEOCODER_API_KEY="")
    @patch("apps.catalog.routing_views.route_legs")
    def test_unconfigured_provider_keeps_origin_controls_available(self, calculate):
        self.assertEqual(self.request().status_code, 503)
        response = self.client.get(reverse("catalog:walk_builder"))
        self.assertNotContains(response, 'data-times-endpoint')
        self.assertContains(response, 'data-walk-locate')
        self.assertContains(response, 'data-walk-origin-open')
        self.assertNotContains(response, 'data-origin-search')
        calculate.assert_not_called()

    @patch("apps.catalog.routing_views.route_legs", side_effect=RoutingUnavailable("private-routing-key"))
    def test_provider_error_is_sanitized_without_fabricated_durations(self, calculate):
        response = self.request()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"error": "routing_unavailable"})
        self.assertIn("no-store", response["Cache-Control"])

    @patch("apps.catalog.routing_views.geocode", return_value=[{"lat": 55.7, "lng": 37.6, "label": "Москва, адрес 1"}])
    def test_forward_and_reverse_geocoding_use_private_server_key(self, resolve):
        url = reverse("catalog:walk_geocode")
        response = self.client.post(url, data=json.dumps({"query": "Москва, адрес 1"}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        resolve.assert_called_with("Москва, адрес 1", "private-geocoder-key", reverse=False)
        response = self.client.post(url, data=json.dumps({"point": {"lat": 55.7, "lng": 37.6}}), content_type="application/json")
        resolve.assert_called_with("37.600000,55.700000", "private-geocoder-key", reverse=True)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertNotIn("private-geocoder-key", response.content.decode())
