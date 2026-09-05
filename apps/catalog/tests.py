from django.test import TestCase
from django.urls import reverse

from .models import Event


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
