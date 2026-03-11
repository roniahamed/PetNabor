from django.db import models
import uuid
from django.conf import settings


class NotificationSettings(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_settings')
    
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
    
