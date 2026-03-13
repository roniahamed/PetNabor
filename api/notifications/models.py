from django.db import models
import uuid
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _


class NotificationSettings(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_settings",
    )

    push_notifications = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    message_notifications = models.BooleanField(default=True)
    friend_request_notifications = models.BooleanField(default=True)
    like_notifications = models.BooleanField(default=True)
    comment_notifications = models.BooleanField(default=True)
    mention_notifications = models.BooleanField(default=True)
    meetup_notifications = models.BooleanField(default=True)
    vendor_post_notifications = models.BooleanField(default=True)
    product_share_notifications = models.BooleanField(default=True)
    product_interest_notifications = models.BooleanField(default=True)
    system_notifications = models.BooleanField(default=True)
    marketing_notifications = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


User = get_user_model()


class FCMDevice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="fcm_devices")
    registration_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return getattr(self.user, "email", str(self.user))


class NotificationTypes(models.TextChoices):
    INFO = "info", _("Info")
    WARNING = "warning", _("Warning")
    ORDER = "order", _("Order Update")
    PROMOTION = "promotion", _("Promotion")
    STREAK_BONUS = "streak_bonus", _("Streak Bonus")
    REFERRAL_BONUS = "referral_bonus", _("Referral Bonus")
    LOGIN = "login", _("Login Notification")
    SUCCESS = "success", _("Success")
    ERROR = "error", _("Error")


class Notifications(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, related_name="notifications", on_delete=models.CASCADE, db_index=True
    )
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True, null=True)
    data = models.JSONField(blank=True, null=True)
    notification_type = models.CharField(
        max_length=20, choices=NotificationTypes.choices, default=NotificationTypes.INFO
    )
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read"]),
        ]
