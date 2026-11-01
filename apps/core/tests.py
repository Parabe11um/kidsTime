from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Account


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


class ProfileSettingsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="profile-parent", email="parent@example.org", password="FamilyCalendar!8537")
        self.account = Account.objects.create(user=self.user, email=self.user.email, privacy_accepted_at=timezone.now(), privacy_policy_url="/privacy/")

    def test_settings_update_only_signed_in_user_and_preserve_privacy_consent(self):
        other = get_user_model().objects.create_user(username="other-parent", first_name="Other")
        self.client.force_login(self.user)
        accepted = self.account.privacy_accepted_at
        response = self.client.post(reverse("core:profile"), {"first_name": "Роман", "last_name": "Сергеев", "newsletter": "on", "user_id": other.pk, "is_staff": "on"})
        self.assertRedirects(response, reverse("core:profile"))
        self.user.refresh_from_db()
        self.account.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(self.user.first_name, "Роман")
        self.assertFalse(self.user.is_staff)
        self.assertEqual(other.first_name, "Other")
        self.assertEqual(self.account.privacy_accepted_at, accepted)
        self.assertIsNotNone(self.account.newsletter_accepted_at)
        self.client.post(reverse("core:profile"), {"first_name": "Роман"})
        self.account.refresh_from_db()
        self.assertIsNone(self.account.newsletter_accepted_at)

    def test_guest_cannot_change_settings(self):
        response = self.client.post(reverse("core:profile"), {"first_name": "Wrong"})
        self.assertRedirects(response, reverse("accounts:login"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "")

    def test_settings_require_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse("core:profile"), {"first_name": "Wrong"}).status_code, 403)

    def test_invalid_name_does_not_save_any_settings(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("core:profile"), {"first_name": "A" * 151, "newsletter": "on"})
        self.assertEqual(response.status_code, 200)
        self.account.refresh_from_db()
        self.assertIsNone(self.account.newsletter_accepted_at)


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
