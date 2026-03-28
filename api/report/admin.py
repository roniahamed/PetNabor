"""
Admin configuration for the Report feature — PetNabor.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.decorators import display

from .models import Report


@admin.register(Report)
class ReportAdmin(UnfoldModelAdmin):
    list_display = (
        "reporter",
        "display_target",
        "reason",
        "display_resolved",
        "created_at",
    )
    list_filter = ("target_type", "is_resolved")
    search_fields = ("reporter__email", "reporter__phone", "reason", "description")
    ordering = ("-created_at", "is_resolved")
    readonly_fields = ("id", "reporter", "target_type", "target_id", "created_at", "updated_at")
    date_hierarchy = "created_at"

    fieldsets = (
        (
            _("Report Details"),
            {
                "fields": ("id", "reporter", "target_type", "target_id"),
            },
        ),
        (
            _("Reason"),
            {
                "fields": ("reason", "description"),
            },
        ),
        (
            _("Resolution"),
            {
                "fields": ("is_resolved",),
            },
        ),
        (
            _("Timestamps"),
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    actions = ["mark_resolved", "mark_unresolved"]

    @admin.action(description="✅ Mark selected reports as resolved")
    def mark_resolved(self, request, queryset):
        count = queryset.update(is_resolved=True)
        self.message_user(request, f"{count} report(s) marked as resolved.")

    @admin.action(description="🔴 Mark selected reports as unresolved")
    def mark_unresolved(self, request, queryset):
        count = queryset.update(is_resolved=False)
        self.message_user(request, f"{count} report(s) marked as unresolved.")

    @display(description=_("Target"), ordering="target_type")
    def display_target(self, obj):
        return f"{obj.target_type} / {str(obj.target_id)[:8]}…"

    @display(description=_("Resolved"), label={True: "success", False: "danger"}, boolean=True)
    def display_resolved(self, obj):
        return obj.is_resolved
