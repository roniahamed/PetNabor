"""
Django signals for the users app.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
import uuid
from .models import Profile


User = get_user_model()


def _generate_referral_code():
    """Generate a short unique referral code (8 uppercase alphanumeric chars)."""
    return uuid.uuid4().hex[:8].upper()


def _unique_referral_code():
    """Keep trying until we get a code that doesn't already exist."""
    while True:
        code = _generate_referral_code()
        if not Profile.objects.filter(referral_code=code).exists():
            return code


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance, referral_code=_unique_referral_code())
    else:
        if hasattr(instance, 'profile'):
            instance.profile.save()
