from django.db import models

class VerificationConfig(models.Model):
    """
    Singleton model to store the price and settings for the Paid App Verification.
    """
    verification_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=9.99,
        help_text="Price for the one-time app verification badge."
    )
    max_persona_attempts = models.IntegerField(
        default=3, 
        help_text="Max times a user can attempt Persona ID verification before being permanently blocked."
    )
    is_active = models.BooleanField(
        default=True, 
        help_text="Toggle to enable/disable the paid verification feature entirely."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Verification Config'
        verbose_name_plural = 'Verification Config'

    def __str__(self):
        return f'Verification Config — ${self.verification_price}'

    @classmethod
    def get_instance(cls):
        """Return the singleton setup row, creating it with defaults if absent."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

