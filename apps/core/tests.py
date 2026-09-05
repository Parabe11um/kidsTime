from django.test import SimpleTestCase, override_settings
from django.urls import reverse


class RobotsPolicyTests(SimpleTestCase):
    @override_settings(ROBOTS_NOINDEX=True)
    def test_noindex_environment_sets_header(self):
        response = self.client.get(reverse("core:health"))

        self.assertEqual(
            response.headers["X-Robots-Tag"],
            "noindex, nofollow, noarchive",
        )

    @override_settings(ROBOTS_NOINDEX=True)
    def test_noindex_robots_file_disallows_crawling(self):
        response = self.client.get(reverse("core:robots_txt"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        self.assertContains(response, "Disallow: /")

    @override_settings(ROBOTS_NOINDEX=False)
    def test_public_robots_file_allows_crawling(self):
        response = self.client.get(reverse("core:robots_txt"))

        self.assertContains(response, "Allow: /")
