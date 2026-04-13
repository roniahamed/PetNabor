import uuid
import os
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.contrib.gis.db import models as gis_models


def vendor_logo_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"vendor_{uuid.uuid4()}.{ext}"
    return os.path.join('vendors/logos/', filename)


# ─────────────────────────────────────────────────────────────
# Vendor Plans
# ─────────────────────────────────────────────────────────────

class PlanName(models.TextChoices):
    BASIC    = 'basic',    'Basic'
    STANDARD = 'standard', 'Standard'
    PRO      = 'pro',      'Pro'


class VendorPlan(models.Model):
    """
    Admin-defined subscription plans available to vendors.
    Each plan controls feature access and product limits.
    """

    name = models.CharField(
        max_length=20,
        choices=PlanName.choices,
        unique=True,
        default=PlanName.BASIC,
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Monthly price in USD.',
    )
    max_products = models.PositiveIntegerField(
        default=10,
        help_text='Maximum number of active products allowed. 0 = unlimited.',
    )

    # Feature flags shown in the plan card
    has_category_top_slot   = models.BooleanField(default=False, help_text='Priority listing placement in category.')
    has_advanced_analytics  = models.BooleanField(default=False, help_text='Access to performance metrics dashboard.')
    has_priority_support    = models.BooleanField(default=False, help_text='Faster response time from support team.')
    has_featured_badge      = models.BooleanField(default=False, help_text='Vendor badge shown on product cards.')

    description = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Vendor Plan'
        verbose_name_plural = 'Vendor Plans'
        ordering            = ['price']

    def __str__(self):
        return f"{self.get_name_display()} — ${self.price}/mo"


# ─────────────────────────────────────────────────────────────
# Vendor
# ─────────────────────────────────────────────────────────────

class Vendor(models.Model):
    id   = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='vendor_profiles',
    )

    logo          = models.ImageField(upload_to=vendor_logo_path, null=True, blank=True)
    business_name = models.CharField(max_length=255)
    descriptions  = models.TextField(blank=True, null=True)

    address_street = models.CharField(max_length=255, null=True, blank=True)
    apartment      = models.CharField(max_length=100,  null=True, blank=True)
    city           = models.CharField(max_length=100,  null=True, blank=True)
    state          = models.CharField(max_length=100,  null=True, blank=True)
    zipcode        = models.CharField(max_length=20,   null=True, blank=True)
    location_point = gis_models.PointField(srid=4326, null=True, blank=True)

    # Plan FK (replaces the old free-text CharField)
    plan = models.ForeignKey(
        VendorPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vendors',
        help_text='Active subscription plan for this vendor.',
    )

    contact_number  = models.CharField(max_length=20,  null=True, blank=True)
    whatsapp_number = models.CharField(max_length=20,  null=True, blank=True)
    website_link    = models.URLField(max_length=500,  null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.business_name


# ─────────────────────────────────────────────────────────────
# Vendor Subscription
# ─────────────────────────────────────────────────────────────

class SubscriptionStatus(models.TextChoices):
    ACTIVE   = 'active',   'Active'
    EXPIRED  = 'expired',  'Expired'
    CANCELED = 'canceled', 'Canceled'


class VendorSubscription(models.Model):
    """
    Tracks the history of plan subscriptions for a vendor.
    The latest active row represents the vendor's current subscription.
    """
    id     = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.CASCADE,
        related_name='subscriptions',
    )
    plan = models.ForeignKey(
        VendorPlan,
        on_delete=models.PROTECT,
        related_name='subscriptions',
    )
    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.ACTIVE,
        db_index=True,
    )
    started_at  = models.DateTimeField()
    expires_at  = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Vendor Subscription'
        verbose_name_plural = 'Vendor Subscriptions'
        ordering            = ['-started_at']

    def __str__(self):
        return f"{self.vendor} → {self.plan} [{self.status}]"
