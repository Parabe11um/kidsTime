from django.conf import settings
from django.urls import reverse


def registration_policy_url():
    """Test accounts acknowledge the local draft; regular accounts use the policy URL."""
    if settings.TEST_REGISTRATION_ENABLED:
        return reverse("core:privacy")
    return settings.PRIVACY_POLICY_URL
