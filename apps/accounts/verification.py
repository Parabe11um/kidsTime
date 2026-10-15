import secrets
from datetime import timedelta
from smtplib import SMTPException

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


MAX_AGE = timedelta(hours=24)
RESEND_INTERVAL = timedelta(minutes=1)


def mail_configured():
    return bool(settings.EMAIL_HOST and settings.DEFAULT_FROM_EMAIL)


def token_digest(account, token):
    # Bind the challenge to this account's current email and password as well.
    identity = f"{account.user_id}:{account.user.email}:{account.user.password}:{token}"
    return salted_hmac("accounts.email_verification", identity, algorithm="sha256").hexdigest()


def pending_verification(account):
    return bool(
        account
        and not account.user.is_active
        and not account.user.is_staff
        and not account.user.is_superuser
        and account.email_verified_at is None
        and account.email_verification_digest
        and account.email_verification_sent_at
        and account.email == account.user.email.strip().lower()
    )


def valid_verification(account, token):
    if not pending_verification(account) or not token or len(token) > 128:
        return False
    age = timezone.now() - account.email_verification_sent_at
    return timedelta() <= age <= MAX_AGE and secrets.compare_digest(
        account.email_verification_digest, token_digest(account, token)
    )


def send_verification(request, account):
    """Caller holds a transaction; failed delivery rolls back a token rotation."""
    token = secrets.token_urlsafe(32)
    account.email_verification_digest = token_digest(account, token)
    account.email_verification_sent_at = timezone.now()
    account.save(update_fields=["email_verification_digest", "email_verification_sent_at"])
    url = request.build_absolute_uri(reverse("accounts:email_verify", kwargs={
        "uidb64": urlsafe_base64_encode(force_bytes(account.user_id)),
        "token": token,
    }))
    body = render_to_string("accounts/email_verification_email.txt", {"verification_url": url})
    if send_mail("Подтвердите email — КидсТайм", body, settings.DEFAULT_FROM_EMAIL, [account.email]) != 1:
        raise SMTPException("Verification email was not accepted")
