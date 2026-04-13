import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from django.db.models import Q

User = get_user_model()

from api.vendor.models import Vendor


# ─────────────────────────────────────────────────────────────
# Category
# ─────────────────────────────────────────────────────────────

class Categories(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name        = models.CharField(max_length=100, unique=True)
    slug        = models.SlugField(max_length=100, unique=True, db_index=True)
    image       = models.ImageField(upload_to='categories', blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name        = 'Category'
        verbose_name_plural = 'Categories'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────
# Brand
# ─────────────────────────────────────────────────────────────

class Brand(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name        = models.CharField(max_length=100, unique=True)
    slug        = models.SlugField(max_length=100, unique=True, db_index=True)
    image       = models.ImageField(upload_to='brands', blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name        = 'Brand'
        verbose_name_plural = 'Brands'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────
# Product
# ─────────────────────────────────────────────────────────────

class Product(models.Model):
    id                   = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor               = models.ForeignKey(Vendor,     on_delete=models.CASCADE, related_name='products')
    slug                 = models.SlugField(max_length=255, unique=True, db_index=True)
    name                 = models.CharField(max_length=255)
    brand                = models.ForeignKey(Brand,      on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    description          = models.TextField(blank=True, null=True)
    price                = models.DecimalField(max_digits=10, decimal_places=2)
    currency             = models.CharField(max_length=3, default='USD')
    category             = models.ForeignKey(Categories, on_delete=models.CASCADE, related_name='products')
    external_product_url = models.URLField(blank=True, null=True)
    is_active            = models.BooleanField(default=True)
    created_at           = models.DateTimeField(auto_now_add=True)
    updated_at           = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name        = 'Product'
        verbose_name_plural = 'Products'
        indexes = [
            models.Index(fields=['category'], name='product_category_idx'),
            models.Index(fields=['vendor'],   name='product_vendor_idx'),
            models.Index(fields=['is_active'], name='product_is_active_idx'),
        ]

    def _generate_slug(self):
        base_slug = slugify(self.name)
        slug = base_slug
        num = 1
        while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f"{base_slug}-{num}"
            num += 1
        return slug

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._generate_slug()
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────
# Product Media
# ─────────────────────────────────────────────────────────────

class MediaType(models.TextChoices):
    IMAGE = 'image', 'Image'
    VIDEO = 'video', 'Video'


class ProductMedia(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product    = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='media')
    file       = models.FileField(upload_to='product_media/')
    thumbnail  = models.ImageField(upload_to='product_media/thumbnails/', blank=True, null=True)
    type       = models.CharField(max_length=10, choices=MediaType.choices, default=MediaType.IMAGE)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Media for {self.product.name} ({'primary' if self.is_primary else 'secondary'})"

    class Meta:
        verbose_name        = 'Product Media'
        verbose_name_plural = 'Product Media'
        constraints = [
            models.UniqueConstraint(
                fields=['product'],
                condition=Q(is_primary=True),
                name='unique_primary_media_per_product',
            )
        ]


# ─────────────────────────────────────────────────────────────
# Product Event
# ─────────────────────────────────────────────────────────────

class EventType(models.TextChoices):
    VIEW       = 'VIEW',       'View'        # product page opened
    CLICK      = 'CLICK',      'Click'       # external link clicked
    IMPRESSION = 'IMPRESSION', 'Impression'  # product shown in a list


class ProductEvent(models.Model):
    """
    Tracks behavioural events on products.

    VIEW       — product detail page was opened.
    CLICK      — vendor's external product URL was clicked.
    IMPRESSION — product appeared in a listing/feed.
    """
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product    = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='events')
    user       = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='product_events',
    )
    event_type = models.CharField(max_length=20, choices=EventType.choices, db_index=True)
    session_id = models.CharField(max_length=128, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata   = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f"{self.event_type} on {self.product.name}"

    class Meta:
        verbose_name        = 'Product Event'
        verbose_name_plural = 'Product Events'
        ordering            = ['-created_at']
        indexes = [
            models.Index(fields=['product'],    name='productevent_product_idx'),
            models.Index(fields=['event_type'], name='productevent_type_idx'),
            models.Index(fields=['created_at'], name='productevent_created_idx'),
        ]
