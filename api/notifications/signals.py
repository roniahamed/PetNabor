"""
Django signals for the notifications app.
"""
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from api.notifications.models import NotificationSettings
from django.db.models.signals import post_save


User = get_user_model()


@receiver(post_save, sender=User)
def create_or_update_user_notification_settings(sender, instance, created, **kwargs):
    if created:
        NotificationSettings.objects.create(user=instance)
    else:
        if hasattr(instance, 'notification_settings'):
            instance.notification_settings.save()