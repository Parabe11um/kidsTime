import re
from datetime import timedelta
from smtplib import SMTPException
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Account


@override_settings(
    TEST_REGISTRATION_ENABLED=False,
    PRIVACY_POLICY_URL="https://example.org/privacy/",
    EMAIL_HOST="smtp.example.org",
    DEFAULT_FROM_EMAIL="support@example.org",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class EmailVerificationTests(TestCase):
    password = "FamilyCalendar!8537"

    def register(self, email="parent@example.org", **kwargs):
        return self.client.post(reverse("accounts:register"), {
            "email": email, "password1": self.password,
            "password2": self.password, "privacy": True,
        }, **kwargs)

    def link(self, index=-1):
        return re.search(r"https?://testserver(/accounts/email/verify/[^\s]+)", mail.outbox[index].body).group(1)

    def make_resend_available(self):
        Account.objects.update(email_verification_sent_at=timezone.now() - timedelta(minutes=2))

    def test_registration_requires_confirmation_then_password_login(self):
        response = self.register(secure=True)
        self.assertRedirects(response, reverse("accounts:email_verification_sent"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("https://testserver/", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ["parent@example.org"])
        user = get_user_model().objects.get()
        self.assertFalse(user.is_active)
        self.assertNotIn("_auth_user_id", self.client.session)
        token = self.link().strip("/").split("/")[-1]
        self.assertNotEqual(user.account.email_verification_digest, token)

        self.client.post(reverse("accounts:login"), {"email": user.email, "password": self.password})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.client.post(reverse("accounts:password_reset"), {"email": user.email})
        self.assertEqual(len(mail.outbox), 1)

        response = self.client.get(self.link())
        self.assertTrue(response.context["validlink"])
        self.assertEqual(response["Referrer-Policy"], "strict-origin")
        user.refresh_from_db()
        self.assertFalse(user.is_active)  # Mail scanners only opening the link cannot activate.
        self.assertRedirects(self.client.post(self.link()), reverse("accounts:email_verified"))
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertIsNotNone(user.account.email_verified_at)
        self.assertEqual(user.account.email_verification_digest, "")
        self.assertNotIn("_auth_user_id", self.client.session)
        response = self.client.post(reverse("accounts:login"), {"email": user.email, "password": self.password})
        self.assertRedirects(response, reverse("core:profile"))

    def test_reused_token_cannot_reactivate_a_blocked_account(self):
        self.register()
        link = self.link()
        self.client.post(link)
        get_user_model().objects.update(is_active=False)
        response = self.client.post(link)
        self.assertFalse(response.context["validlink"])
        self.assertFalse(get_user_model().objects.get().is_active)

    def test_expired_token_is_rejected(self):
        self.register()
        Account.objects.update(email_verification_sent_at=timezone.now() - timedelta(hours=24, seconds=1))
        response = self.client.post(self.link())
        self.assertFalse(response.context["validlink"])
        self.assertFalse(get_user_model().objects.get().is_active)

    def test_password_reset_and_activation_tokens_are_not_interchangeable(self):
        self.register()
        user = get_user_model().objects.get()
        link = self.link()
        reset_token = default_token_generator.make_token(user)
        wrong_link = link.rsplit("/", 2)[0] + "/" + reset_token + "/"
        self.assertFalse(self.client.post(wrong_link).context["validlink"])
        activation_token = link.strip("/").split("/")[-1]
        self.assertFalse(default_token_generator.check_token(user, activation_token))

    def test_forged_token_or_wrong_account_cannot_activate(self):
        self.register()
        first = self.link()
        self.register("other@example.org")
        second = self.link()
        wrong_account = second.rsplit("/", 2)[0] + "/" + first.strip("/").split("/")[-1] + "/"
        forged = first.rsplit("/", 2)[0] + "/invalid-token/"
        for link in (forged, wrong_account, "/accounts/email/verify/invalid/token/"):
            with self.subTest(link=link):
                response = self.client.post(link)
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.context["validlink"])
        self.assertFalse(get_user_model().objects.filter(is_active=True).exists())

    def test_email_or_password_change_invalidates_token(self):
        self.register()
        user = get_user_model().objects.get()
        user.email = "changed@example.org"
        user.save(update_fields=["email"])
        self.assertFalse(self.client.post(self.link()).context["validlink"])
        user.email = "parent@example.org"
        user.set_password("OtherCalendar!9437")
        user.save(update_fields=["email", "password"])
        self.assertFalse(self.client.post(self.link()).context["validlink"])
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_resend_replaces_old_link_after_cooldown(self):
        self.register()
        old = self.link()
        self.make_resend_available()
        response = self.client.post(reverse("accounts:email_verification_resend"), {"email": "PARENT@example.org"})
        self.assertRedirects(response, reverse("accounts:email_verification_sent"))
        self.assertEqual(len(mail.outbox), 2)
        self.assertFalse(self.client.get(old).context["validlink"])
        self.assertTrue(self.client.get(self.link()).context["validlink"])

    def test_cooldown_unknown_active_and_legacy_blocked_get_same_response(self):
        self.register()
        User = get_user_model()
        User.objects.create_user("legacy", email="active@example.org", password=self.password)
        User.objects.create_user("blocked", email="blocked@example.org", password=self.password, is_active=False)
        for email in ("parent@example.org", "unknown@example.org", "active@example.org", "blocked@example.org"):
            response = self.client.post(reverse("accounts:email_verification_resend"), {"email": email})
            self.assertRedirects(response, reverse("accounts:email_verification_sent"))
        self.assertEqual(len(mail.outbox), 1)

    def test_smtp_failure_rolls_back_registration(self):
        with patch("apps.accounts.verification.send_mail", side_effect=SMTPException("delivery failed")):
            response = self.register()
        self.assertContains(response, "Не удалось отправить письмо подтверждения")
        self.assertFalse(Account.objects.exists())
        self.assertFalse(get_user_model().objects.exists())

    def test_smtp_failure_during_resend_preserves_previous_link(self):
        self.register()
        old = self.link()
        self.make_resend_available()
        with patch("apps.accounts.verification.send_mail", side_effect=SMTPException("delivery failed")):
            response = self.client.post(reverse("accounts:email_verification_resend"), {"email": "parent@example.org"})
        self.assertContains(response, "Не удалось отправить письмо")
        self.assertTrue(self.client.get(old).context["validlink"])

    @override_settings(EMAIL_HOST="")
    def test_registration_without_smtp_is_unavailable(self):
        response = self.register()
        self.assertContains(response, "отправка писем ещё не настроена")
        self.assertFalse(Account.objects.exists())

    def test_resend_rate_limit_prevents_delivery(self):
        self.register()
        self.make_resend_available()
        with patch("apps.accounts.views.rate_limited", return_value=True):
            response = self.client.post(reverse("accounts:email_verification_resend"), {"email": "parent@example.org"})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(len(mail.outbox), 1)

    def test_activation_and_resend_require_csrf(self):
        self.register()
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(self.link()).status_code, 403)
        self.assertEqual(client.post(reverse("accounts:email_verification_resend"), {"email": "parent@example.org"}).status_code, 403)
        self.assertFalse(get_user_model().objects.get().is_active)

    @override_settings(CSRF_COOKIE_SECURE=True)
    def test_https_confirmation_accepts_valid_csrf_with_origin_only_referrer(self):
        self.register(secure=True)
        client = Client(enforce_csrf_checks=True)
        page = client.get(self.link(), secure=True)
        csrf = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode()).group(1)

        # An HTTPS browser following no-referrer fails even with a valid CSRF token.
        with self.assertLogs("django.security.csrf", level="WARNING") as logs:
            rejected = client.post(self.link(), {"csrfmiddlewaretoken": csrf}, secure=True)
        self.assertEqual(rejected.status_code, 403)
        self.assertIn("no Referer", " ".join(logs.output))
        self.assertFalse(get_user_model().objects.get().is_active)

        with self.assertLogs("django.security.csrf", level="WARNING"):
            rejected = client.post(self.link(), {"csrfmiddlewaretoken": csrf}, secure=True, HTTP_ORIGIN="null")
        self.assertEqual(rejected.status_code, 403)

        self.assertEqual(page["Referrer-Policy"], "strict-origin")
        self.assertContains(page, 'name="referrer" content="strict-origin"')
        response = client.post(self.link(), {"csrfmiddlewaretoken": csrf}, secure=True, HTTP_REFERER="https://testserver/")
        self.assertRedirects(response, reverse("accounts:email_verified"))
        self.assertEqual(response["Referrer-Policy"], "strict-origin")
        self.assertTrue(get_user_model().objects.get().is_active)

    @override_settings(CSRF_COOKIE_SECURE=True)
    def test_https_confirmation_accepts_browser_origin_through_proxy(self):
        self.register(secure=True)
        client = Client(enforce_csrf_checks=True, HTTP_HOST="testserver")
        page = client.get(self.link(), HTTP_X_FORWARDED_PROTO="https")
        csrf = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode()).group(1)
        response = client.post(
            self.link(), {"csrfmiddlewaretoken": csrf},
            HTTP_X_FORWARDED_PROTO="https", HTTP_ORIGIN="https://testserver", HTTP_REFERER="https://testserver/",
        )
        self.assertRedirects(response, reverse("accounts:email_verified"))
        self.assertTrue(get_user_model().objects.get().is_active)

    def test_https_confirmation_rejects_foreign_origin_even_with_valid_csrf(self):
        self.register(secure=True)
        client = Client(enforce_csrf_checks=True)
        page = client.get(self.link(), secure=True)
        csrf = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode()).group(1)
        for headers in (
            {"HTTP_ORIGIN": "https://untrusted.example", "HTTP_REFERER": "https://testserver/"},
            {"HTTP_REFERER": "https://untrusted.example/"},
        ):
            with self.subTest(headers=headers), self.assertLogs("django.security.csrf", level="WARNING"):
                response = client.post(self.link(), {"csrfmiddlewaretoken": csrf}, secure=True, **headers)
                self.assertEqual(response.status_code, 403)
        self.assertFalse(get_user_model().objects.get().is_active)

    def test_staff_account_cannot_be_activated_by_registration_token(self):
        self.register()
        get_user_model().objects.update(is_staff=True)
        response = self.client.post(self.link())
        self.assertFalse(response.context["validlink"])
        self.assertFalse(get_user_model().objects.get().is_active)
