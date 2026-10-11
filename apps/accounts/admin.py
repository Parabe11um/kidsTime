from django.contrib import admin

from .models import Account


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("email", "privacy_accepted_at", "newsletter_accepted_at")
    search_fields = ("email",)
    readonly_fields = ("user", "email", "privacy_accepted_at", "privacy_policy_url", "newsletter_accepted_at")

    def has_add_permission(self, request):
        return False
