"""
Admin configuration for User, Profile, and OTPVerification.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import OTPVerification, Profile, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "email",
        "phone",
        "is_verified",
        "is_email_verified",
        "is_phone_verified",
        "is_staff",
        "is_active",
        "created_at",
    )
    list_filter = ("is_staff", "is_active", "is_verified", "is_email_verified", "is_phone_verified", "user_type")
    search_fields = ("username", "email", "phone", "first_name", "last_name")
    ordering = ("-created_at",)
    readonly_fields = ("id", "created_at", "updated_at", "firebase_uid")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "bio", "display_profile_picture")
    search_fields = ("user__email", "user__username")
    ordering = ("user__id",)
    raw_id_fields = ("user", "referred_by")

    def display_profile_picture(self, obj):
        if obj.profile_picture:
            return format_html(
                '<img src="{}" width="50" height="50" style="border-radius: 50%;" />',
                obj.profile_picture.url,
            )
        return "-"

    display_profile_picture.short_description = "Profile Picture"


@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ("user", "otp_type", "is_used", "attempt_count", "expires_at", "created_at")
    list_filter = ("otp_type", "is_used")
    search_fields = ("user__email", "user__phone")
    ordering = ("-created_at",)
    readonly_fields = ("id", "otp_hash", "created_at")
    raw_id_fields = ("user",)
