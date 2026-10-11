from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
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


@override_settings(TEST_REGISTRATION_ENABLED=False, PRIVACY_POLICY_URL="")
class PrivacyDraftTests(TestCase):
    def test_draft_is_accessible_and_explicit_about_temporary_operator(self):
        response = self.client.get(reverse("core:privacy"))
        self.assertContains(response, "ООО «Кидстайм»")
        self.assertContains(response, "Компания ещё не зарегистрирована")
        self.assertContains(response, "mailto:info@kidstime.devtestenv.ru")
        self.assertContains(response, 'name="robots" content="noindex, nofollow, noarchive"')
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow, noarchive")

    @override_settings(TEST_REGISTRATION_ENABLED=True)
    def test_draft_discloses_open_test_registration(self):
        response = self.client.get(reverse("core:privacy"))
        self.assertContains(response, "Тестовая регистрация открыта.")
        self.assertContains(response, "Компания ещё не зарегистрирована")
        self.assertNotContains(response, "Этот черновик не используется")

    def test_profile_and_disabled_registration_link_to_draft(self):
        for name in ("core:profile", "accounts:register"):
            with self.subTest(page=name):
                self.assertContains(self.client.get(reverse(name)), 'href="/privacy/"')

    def test_adding_draft_does_not_enable_registration(self):
        response = self.client.post(reverse("accounts:register"), {
            "email": "parent@example.org",
            "password1": "FamilyCalendar!8537",
            "password2": "FamilyCalendar!8537",
            "privacy": True,
        })
        self.assertContains(response, "политика конфиденциальности ещё не опубликована")
        self.assertFalse(get_user_model().objects.filter(email="parent@example.org").exists())
