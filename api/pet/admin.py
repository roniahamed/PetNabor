"""
Admin configuration for the PetProfile — PetNabor.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.decorators import display

from .models import PetProfile


@admin.register(PetProfile)
class PetProfileAdmin(UnfoldModelAdmin):
    list_display = (
        "display_avatar",
        "pet_name",
        "pet_type",
        "size",
        "display_weight",
        "vaccination_status",
        "user",
        "created_at",
    )
    list_filter = ("pet_type", "size", "weight_type", "vaccination_status")
    search_fields = ("pet_name", "user__email", "user__username", "pet_type")
    ordering = ("-created_at",)
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = ("user",)
    date_hierarchy = "created_at"

    fieldsets = (
        (
            _("Basic Info"),
            {
                "fields": ("id", "user", "pet_name", "pet_type", "image"),
            },
        ),
        (
            _("Physical Details"),
            {
                "fields": ("size", "weight", "weight_type", "date_of_birth"),
            },
        ),
        (
            _("Health"),
            {
                "fields": ("vaccination_status", "vaccination_document", "vet_contact_number"),
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

    @display(description=_("Photo"))
    def display_avatar(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="48" height="48" style="border-radius:8px;object-fit:cover;" />',
                obj.image.url,
            )
        return format_html("<span style='font-size:28px'>🐾</span>")

    @display(description=_("Weight"), ordering="weight")
    def display_weight(self, obj):
        return f"{obj.weight} {obj.weight_type}"
