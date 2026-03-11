from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Profile, NotificationSettings

User = get_user_model()

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
        NotificationSettings.objects.create(user=instance)
    else:
        if hasattr(instance, 'profile'):
            instance.profile.save()
        if hasattr(instance, 'notification_settings'):
            instance.notification_settings.save()