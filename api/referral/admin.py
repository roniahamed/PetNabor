"""
Referral admin.
"""
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse

from .models import ReferralSettings, ReferralTransaction, ReferralWallet


@admin.register(ReferralSettings)
class ReferralSettingsAdmin(admin.ModelAdmin):
    """
    Singleton admin: prevents creating more than one settings row.
    """
    list_display = ["referrer_points", "referee_points", "updated_at"]
    readonly_fields = ["created_at", "updated_at"]

    def has_add_permission(self, request):
        # Only allow adding if no record exists yet
        return not ReferralSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        """Redirect straight to the single setting record (or add page)."""
        obj = ReferralSettings.objects.first()
        if obj:
            url = reverse(
                f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_change",
                args=[obj.pk],
            )
        else:
            url = reverse(
                f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_add"
            )
        return HttpResponseRedirect(url)


@admin.register(ReferralWallet)
class ReferralWalletAdmin(admin.ModelAdmin):
    list_display = ["user", "balance", "updated_at"]
    search_fields = ["user__email", "user__phone"]
    readonly_fields = ["id", "user", "balance", "created_at", "updated_at"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReferralTransaction)
class ReferralTransactionAdmin(admin.ModelAdmin):
    list_display = ["wallet", "transaction_type", "amount", "status", "related_user", "created_at"]
    list_filter = ["transaction_type", "status"]
    search_fields = ["wallet__user__email", "related_user__email", "note"]
    readonly_fields = [f.name for f in ReferralTransaction._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
