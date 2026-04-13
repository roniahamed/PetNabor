from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(ModelAdmin):
    list_display = ('site_name', 'maintenance_mode', 'allow_vendor_registration', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Branding', {
            'fields': ('site_name', 'site_logo', 'contact_email'),
        }),
        ('Platform Toggles', {
            'fields': ('maintenance_mode', 'allow_vendor_registration', 'allow_user_registration'),
        }),
        ('Product / Feed', {
            'fields': ('featured_category', 'products_per_page'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def has_add_permission(self, request):
        # Only allow one instance
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
