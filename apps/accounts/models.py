from django.conf import settings
from django.db import models


class Account(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="account")
    email = models.EmailField("Email при регистрации", unique=True)
    privacy_accepted_at = models.DateTimeField("Политика принята")
    privacy_policy_url = models.CharField("Принятая политика", max_length=500)
    newsletter_accepted_at = models.DateTimeField("Согласие на рассылку", null=True, blank=True)
    email_verified_at = models.DateTimeField("Email подтверждён", null=True, blank=True, editable=False)
    email_verification_digest = models.CharField(max_length=64, blank=True, default="", editable=False)
    email_verification_sent_at = models.DateTimeField("Письмо подтверждения отправлено", null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "Аккаунт"
        verbose_name_plural = "Аккаунты"

    def __str__(self):
        return self.email


class AuthAttempt(models.Model):
    key = models.CharField(max_length=64, unique=True)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)
