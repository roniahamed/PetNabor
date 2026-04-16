from django.contrib import admin
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from .models import VerificationConfig

@admin.register(VerificationConfig)
class VerificationConfigAdmin(UnfoldModelAdmin):
    list_display = ('verification_price', 'max_persona_attempts', 'is_active', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')

    def has_add_permission(self, request):
        return not VerificationConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

