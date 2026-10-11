import hashlib
from datetime import timedelta

from django.conf import settings
from django.db.models import F
from django.utils import timezone

from .models import AuthAttempt


def rate_limited(request, action, email=""):
    """Shared database counters work across Gunicorn workers; no passwords are recorded."""
    now = timezone.now()
    seconds = 900 if action == "login" else 3600
    bucket = int(now.timestamp()) // seconds
    ip = request.META.get("REMOTE_ADDR", "unknown")
    if settings.AUTH_TRUST_PROXY_IP:
        ip = request.META.get("HTTP_X_FORWARDED_FOR", ip).split(",")[0].strip()
    rules = [("ip", ip, 100 if action == "login" else 20)]
    if email:
        rules.append(("email", email.strip().lower(), 20 if action == "login" else 5))
    AuthAttempt.objects.filter(expires_at__lt=now).delete()
    limited = False
    for kind, value, limit in rules:
        key = hashlib.sha256(f"{action}:{kind}:{value}:{bucket}".encode()).hexdigest()
        counter, _ = AuthAttempt.objects.get_or_create(key=key, defaults={"expires_at": now + timedelta(seconds=seconds)})
        AuthAttempt.objects.filter(pk=counter.pk).update(count=F("count") + 1)
        counter.refresh_from_db(fields=["count"])
        limited = limited or counter.count > limit
    return limited
