from django.contrib import admin
from .models import NotificationSettings, Notifications, FCMDevice


@admin.register(NotificationSettings)
class NotificationSettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "email_notifications", "push_notifications")
    search_fields = ("user__email", "user__username")
    ordering = ("user__id",)


@admin.register(Notifications)
class NotificationsAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "body", "created_at", "is_read")
    search_fields = ("user__email", "user__username", "title", "body")
    ordering = ("-created_at",)


@admin.register(FCMDevice)
class FCMDeviceAdmin(admin.ModelAdmin):
    list_display = ("user", "registration_id")
    search_fields = ("user__email", "user__username", "registration_id")
