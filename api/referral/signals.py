"""
Referral signals.

Listens for Profile saves and awards referral points the first time
referred_by is populated (i.e., when the new user's profile is saved
after they used a referral code during signup).
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from api.users.models import Profile


@receiver(post_save, sender=Profile)
def on_profile_saved(sender, instance, created, **kwargs):
    """Award points when a profile has a referral (guard in service prevents double-award)."""
    if instance.referred_by:
        # Import here to avoid circular imports at module load time
        from .services import award_referral_points
        award_referral_points(instance.user)
