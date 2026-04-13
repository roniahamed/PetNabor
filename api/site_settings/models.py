"""
Site Settings — global singleton model for admin-configurable settings.

Follows the same singleton pattern as ReferralSettings.
"""

from django.db import models
from django.conf import settings


class SiteSettings(models.Model):
    """
    A singleton model for site-wide configuration.
    There should only ever be ONE row in this table.

    Access via:  SiteSettings.get_instance()
    """

    # ── Branding ──────────────────────────────────────────────
    site_name = models.CharField(
        max_length=100,
        default='PetNabor',
        help_text='Displayed in email templates and the admin header.',
    )
    site_logo = models.ImageField(
        upload_to='site_settings/',
        null=True,
        blank=True,
        help_text='Main site logo used in emails and frontend.',
    )
    contact_email = models.EmailField(
        default='',
        blank=True,
        help_text='Primary contact email shown on the platform.',
    )

    # ── Platform Toggles ──────────────────────────────────────
    maintenance_mode = models.BooleanField(
        default=False,
        help_text='When enabled, API returns 503 for non-admin requests.',
    )
    allow_vendor_registration = models.BooleanField(
        default=True,
        help_text='Toggle whether new vendors can register.',
    )
    allow_user_registration = models.BooleanField(
        default=True,
        help_text='Toggle whether new users can sign up.',
    )

    # ── Product / Feed Settings ────────────────────────────────
    featured_category = models.ForeignKey(
        'product.Categories',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        help_text='Category pinned to the top of the product feed.',
    )
    products_per_page = models.PositiveIntegerField(
        default=20,
        help_text='Default page size for product listings.',
    )

    # ── Timestamps ────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Site Settings'
        verbose_name_plural = 'Site Settings'

    def __str__(self):
        return f'Site Settings — {self.site_name}'

    @classmethod
    def get_instance(cls):
        """Return the singleton settings row, creating it with defaults if absent."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
