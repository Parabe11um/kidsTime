import re
from unittest.mock import patch

from django.contrib.auth import authenticate, get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.catalog.management.commands.seed_demo import Command as SeedCommand
from apps.catalog.models import Event
from apps.favorites.models import Favorite
from .models import Account, AuthAttempt

PASSWORD = "FamilyCalendar!8537"


@override_settings(TEST_REGISTRATION_ENABLED=False, PRIVACY_POLICY_URL="https://example.org/privacy/", EMAIL_HOST="smtp.example.org", DEFAULT_FROM_EMAIL="support@example.org", EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AccountFlowTests(TestCase):
    def registration(self, **kwargs):
        return {"email": "Parent@Example.org", "password1": PASSWORD, "password2": PASSWORD, "privacy": True, **kwargs}

    def test_register_creates_normalized_nonstaff_user_and_records_consents(self):
        response = self.client.post(reverse("accounts:register"), self.registration(newsletter=True))
        self.assertRedirects(response, reverse("accounts:email_verification_sent"))
        user = get_user_model().objects.get(email="parent@example.org")
        self.assertTrue(user.check_password(PASSWORD))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_active)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIsNotNone(user.account.privacy_accepted_at)
        self.assertIsNotNone(user.account.newsletter_accepted_at)

    def test_marketing_consent_is_optional_and_unchecked(self):
        response = self.client.get(reverse("accounts:register"))
        self.assertFalse(response.context["form"].fields["newsletter"].initial)
        self.client.post(reverse("accounts:register"), self.registration())
        self.assertIsNone(Account.objects.get().newsletter_accepted_at)

    def test_register_rejects_invalid_password_missing_consent_and_mismatch(self):
        for changes in ({"password1": "12345678", "password2": "12345678"}, {"privacy": False}, {"password2": "SomethingElse!49"}):
            response = self.client.post(reverse("accounts:register"), self.registration(**changes))
            self.assertEqual(response.status_code, 200)
            self.assertFalse(get_user_model().objects.exists())

    @override_settings(PRIVACY_POLICY_URL="")
    def test_registration_requires_published_policy(self):
        self.client.post(reverse("accounts:register"), self.registration())
        self.assertFalse(get_user_model().objects.exists())

    @override_settings(TEST_REGISTRATION_ENABLED=True, PRIVACY_POLICY_URL="")
    def test_test_registration_uses_draft_and_creates_account(self):
        page = self.client.get(reverse("accounts:register"))
        self.assertContains(page, "Тестовая регистрация.")
        self.assertContains(page, 'href="/privacy/"')
        self.assertEqual(page.context["privacy_policy_url"], "/privacy/")
        response = self.client.post(reverse("accounts:register"), self.registration())
        self.assertRedirects(response, reverse("accounts:email_verification_sent"))
        account = Account.objects.get()
        self.assertEqual(account.privacy_policy_url, "/privacy/")
        self.assertIsNotNone(account.privacy_accepted_at)
        self.assertFalse(account.user.is_staff)
        self.assertFalse(account.user.is_superuser)
        self.assertFalse(account.user.is_active)
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(TEST_REGISTRATION_ENABLED=True, PRIVACY_POLICY_URL="")
    def test_test_registration_still_requires_draft_acknowledgment(self):
        response = self.client.post(reverse("accounts:register"), self.registration(privacy=False))
        self.assertFormError(response.context["form"], "privacy", "Необходимо ознакомиться с черновиком политики тестовой версии.")
        self.assertFalse(get_user_model().objects.exists())

    def test_disabling_test_mode_keeps_existing_account_login_available(self):
        with override_settings(TEST_REGISTRATION_ENABLED=True, PRIVACY_POLICY_URL=""):
            self.client.post(reverse("accounts:register"), self.registration())
            url = re.search(r"http://testserver(/accounts/email/verify/[^\s]+)", mail.outbox[-1].body).group(1)
            self.client.post(url)
        self.client.post(reverse("accounts:logout"))
        with override_settings(TEST_REGISTRATION_ENABLED=False, PRIVACY_POLICY_URL=""):
            page = self.client.get(reverse("accounts:register"))
            self.assertEqual(page.context["privacy_policy_url"], "")
            self.client.post(reverse("accounts:register"), self.registration(email="second@example.org"))
            self.assertEqual(Account.objects.count(), 1)
            response = self.client.post(reverse("accounts:login"), {"email": "parent@example.org", "password": PASSWORD})
            self.assertRedirects(response, reverse("core:profile"))

    def test_case_insensitive_duplicate_email_including_legacy_account(self):
        get_user_model().objects.create_user("legacy-admin", email="PARENT@example.org", password=PASSWORD)
        response = self.client.post(reverse("accounts:register"), self.registration())
        self.assertFormError(response.context["form"], "email", "Этот email уже зарегистрирован. Войдите или восстановите пароль.")
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_email_login_safe_next_and_post_only_logout(self):
        user = get_user_model().objects.create_user("legacy", email="parent@example.org", password=PASSWORD)
        response = self.client.post(reverse("accounts:login"), {"email": "PARENT@example.org", "password": PASSWORD, "next": "https://attacker.example/"})
        self.assertRedirects(response, reverse("core:profile"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
        self.client.post(reverse("accounts:logout"))
        self.assertNotIn("_auth_user_id", self.client.session)
        response = self.client.post(reverse("accounts:login"), {"email": user.email, "password": PASSWORD, "next": "/favorites/"})
        self.assertRedirects(response, "/favorites/")

    def test_ambiguous_or_inactive_email_cannot_login_but_admin_username_still_works(self):
        user = get_user_model().objects.create_user("admin", email="parent@example.org", password=PASSWORD)
        get_user_model().objects.create_user("other", email="parent@example.org", password=PASSWORD)
        self.assertIsNone(authenticate(email=user.email, password=PASSWORD))
        self.assertEqual(authenticate(username="admin", password=PASSWORD), user)
        user.is_active = False
        user.email = "inactive@example.org"
        user.save()
        self.assertIsNone(authenticate(email=user.email, password=PASSWORD))

    def test_auth_post_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        for name in ("register", "login", "password_reset"):
            self.assertEqual(client.post(reverse("accounts:" + name), self.registration()).status_code, 403)

    def test_login_rate_limit_does_not_authenticate(self):
        user = get_user_model().objects.create_user("parent", email="parent@example.org", password=PASSWORD)
        with patch("apps.accounts.views.rate_limited", return_value=True):
            response = self.client.post(reverse("accounts:login"), {"email": user.email, "password": PASSWORD})
        self.assertEqual(response.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_real_database_rate_counters_limit_attempts(self):
        from django.test import RequestFactory
        from .limits import rate_limited
        request = RequestFactory().post("/accounts/login/")
        for _ in range(20):
            self.assertFalse(rate_limited(request, "login", "parent@example.org"))
        self.assertTrue(rate_limited(request, "login", "PARENT@example.org"))
        self.assertEqual(AuthAttempt.objects.count(), 2)

    def test_reset_email_and_single_use_token(self):
        user = get_user_model().objects.create_user("parent", email="parent@example.org", password=PASSWORD)
        response = self.client.post(reverse("accounts:password_reset"), {"email": user.email})
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        url = re.search(r"http://testserver(/accounts/password/reset/[^\s]+)", mail.outbox[0].body).group(1)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        password_form_url = response.url
        new_password = "DifferentCalendar!8719"
        response = self.client.post(password_form_url, {"new_password1": new_password, "new_password2": new_password})
        self.assertRedirects(response, reverse("accounts:password_reset_complete"))
        user.refresh_from_db()
        self.assertTrue(user.check_password(new_password))
        self.assertFalse(self.client.get(url).context["validlink"])

    def test_reset_unknown_email_has_same_success_page_without_email(self):
        response = self.client.post(reverse("accounts:password_reset"), {"email": "unknown@example.org"})
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_HOST="")
    def test_reset_without_smtp_reports_unavailability(self):
        response = self.client.post(reverse("accounts:password_reset"), {"email": "parent@example.org"})
        self.assertContains(response, "Восстановление пароля временно недоступно")
        self.assertEqual(len(mail.outbox), 0)

    def test_forged_reset_token_is_rejected(self):
        user = get_user_model().objects.create_user("parent", email="parent@example.org", password=PASSWORD)
        response = self.client.get(reverse("accounts:password_reset_confirm", args=[urlsafe_base64_encode(force_bytes(user.pk)), "invalid-token"]))
        self.assertFalse(response.context["validlink"])

    def test_screens_render_and_have_no_social_login(self):
        for name in ("login", "register", "password_reset", "password_reset_done", "password_reset_complete"):
            response = self.client.get(reverse("accounts:" + name))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, "Войти с помощью")
        self.assertContains(self.client.get(reverse("core:profile")), "Зарегистрироваться")


class AccountFavoritesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        SeedCommand().handle(dry_run=False)
        cls.user = get_user_model().objects.create_user("parent", email="parent@example.org", password=PASSWORD)
        cls.other = get_user_model().objects.create_user("other", email="other@example.org", password=PASSWORD)
        cls.event = Event.objects.visible().first()

    def test_account_favorites_are_isolated_and_set_is_idempotent(self):
        self.client.force_login(self.user)
        url = reverse("favorites:set", args=[self.event.pk])
        for _ in range(2):
            response = self.client.post(url, {"favorite": True}, content_type="application/json")
            self.assertEqual(response.json()["ids"], [self.event.pk])
        self.assertEqual(Favorite.objects.filter(user=self.user).count(), 1)
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse("favorites:cards"), {"ids": self.event.pk}), self.event.title)
        self.client.post(url, {"favorite": False}, content_type="application/json")
        self.assertTrue(Favorite.objects.filter(user=self.user).exists())

    def test_guest_merge_filters_nonpublic_ids_and_keeps_existing_favorites(self):
        self.client.force_login(self.user)
        unpublished = Event.objects.exclude(pk=self.event.pk).first()
        unpublished.status = "draft"
        unpublished.save()
        Favorite.objects.create(user=self.user, event=self.event)
        response = self.client.post(reverse("favorites:merge"), {"ids": [self.event.pk, unpublished.pk, 999999]}, content_type="application/json")
        self.assertEqual(response.json()["ids"], [self.event.pk])
        self.assertEqual(Favorite.objects.filter(user=self.user).count(), 1)

    def test_favorite_write_requires_login_and_csrf(self):
        url = reverse("favorites:set", args=[self.event.pk])
        self.assertEqual(self.client.post(url, {"favorite": True}, content_type="application/json").status_code, 302)
        secure_client = Client(enforce_csrf_checks=True)
        secure_client.force_login(self.user)
        self.assertEqual(secure_client.post(url, {"favorite": True}, content_type="application/json").status_code, 403)
