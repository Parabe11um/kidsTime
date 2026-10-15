from django.contrib import admin

from .models import Account


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("email", "email_verified_at", "privacy_accepted_at", "newsletter_accepted_at")
    search_fields = ("email",)
    readonly_fields = ("user", "email", "email_verified_at", "email_verification_sent_at", "privacy_accepted_at", "privacy_policy_url", "newsletter_accepted_at")

    def has_add_permission(self, request):
        return False
