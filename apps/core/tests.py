import io
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

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

    def test_drawer_settings_return_to_the_original_local_page(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("core:profile"), {"first_name": "Роман", "next": "/events/?q=семья"})
        self.assertRedirects(response, "/events/?q=семья", fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Роман")

    def test_settings_return_url_cannot_redirect_outside_the_application(self):
        self.client.force_login(self.user)
        for target in ("https://outside.example/", "//outside.example/", "javascript:alert(1)", "\\\\outside.example/", "http://testserver/events/"):
            with self.subTest(target=target):
                response = self.client.post(reverse("core:profile"), {"first_name": "Роман", "next": target}, secure=True)
                self.assertRedirects(response, reverse("core:profile"), fetch_redirect_response=False)


class ProfileAvatarTests(TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.media_root = Path(directory.name)
        media_settings = override_settings(MEDIA_ROOT=directory.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)
        self.user = get_user_model().objects.create_user(username="photo-parent", email="photo@example.org")
        self.account = Account.objects.create(user=self.user, email=self.user.email, privacy_accepted_at=timezone.now(), privacy_policy_url="/privacy/")
        self.client.force_login(self.user)

    def photo(self, *, size=(900, 600), suffix=b""):
        output = io.BytesIO()
        metadata = Image.Exif()
        metadata[305] = "private-photo-metadata"
        Image.new("RGB", size, "#abd8cf").save(output, format="JPEG", exif=metadata)
        return SimpleUploadedFile("original-private-name.jpg", output.getvalue() + suffix, content_type="image/jpeg")

    def test_photo_updates_only_current_account_and_is_reencoded(self):
        other = get_user_model().objects.create_user(username="other-photo-parent", email="other-photo@example.org")
        other_account = Account.objects.create(user=other, email=other.email, privacy_accepted_at=timezone.now(), privacy_policy_url="/privacy/")
        response = self.client.post(reverse("core:profile_avatar"), {"avatar": self.photo(suffix=b"<script>trailing payload</script>"), "user_id": other.pk})
        self.assertRedirects(response, reverse("core:profile"))
        self.account.refresh_from_db()
        other_account.refresh_from_db()
        self.assertFalse(other_account.avatar)
        self.assertRegex(self.account.avatar.name, r"^avatars/[0-9a-f]{32}\.jpg$")
        saved = self.media_root / self.account.avatar.name
        with Image.open(saved) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertLessEqual(max(image.size), 512)
            self.assertFalse(image.getexif())
        self.assertNotIn(b"trailing payload", saved.read_bytes())
        self.assertContains(self.client.get(reverse("core:profile")), self.account.avatar.url)

    def test_invalid_or_unsupported_upload_does_not_create_a_file(self):
        for name, content, content_type in (
            ("icon.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', "image/svg+xml"),
            ("broken.jpg", b"not an image", "image/jpeg"),
        ):
            with self.subTest(name=name):
                response = self.client.post(reverse("core:profile_avatar"), {"avatar": SimpleUploadedFile(name, content, content_type=content_type)})
                self.assertRedirects(response, reverse("core:profile"))
                self.account.refresh_from_db()
                self.assertFalse(self.account.avatar)
        self.assertEqual(list(self.media_root.rglob("*")), [])

    def test_oversize_or_high_resolution_photo_is_rejected(self):
        for photo in (self.photo(suffix=b"x" * (5 * 1024 * 1024)), self.photo(size=(4097, 4096))):
            with self.subTest(size=photo.size):
                self.client.post(reverse("core:profile_avatar"), {"avatar": photo})
                self.account.refresh_from_db()
                self.assertFalse(self.account.avatar)
        self.assertEqual(list(self.media_root.rglob("*")), [])

    def test_animated_photo_is_rejected(self):
        output = io.BytesIO()
        Image.new("RGB", (20, 20), "red").save(output, format="PNG", save_all=True, append_images=[Image.new("RGB", (20, 20), "blue")], duration=100, loop=0)
        self.client.post(reverse("core:profile_avatar"), {"avatar": SimpleUploadedFile("animated.png", output.getvalue(), content_type="image/png")})
        self.account.refresh_from_db()
        self.assertFalse(self.account.avatar)

    def test_photo_requires_login_post_and_csrf(self):
        self.assertEqual(self.client.get(reverse("core:profile_avatar")).status_code, 405)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse("core:profile_avatar"), {"avatar": self.photo()}).status_code, 403)
        self.client.logout()
        response = self.client.post(reverse("core:profile_avatar"), {"avatar": self.photo()})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:login")))
        self.account.refresh_from_db()
        self.assertFalse(self.account.avatar)


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
