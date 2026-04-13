import uuid
from django.db import models
from django.conf import settings

from api.product.models import Product


class ProductWishlist(models.Model):
    """
    Allows users to bookmark products they are interested in.
    A user can only wishlist the same product once (unique_together constraint).
    """
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product    = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='wishlists',
    )
    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='product_wishlists',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} → {self.product.name}"

    class Meta:
        verbose_name        = 'Product Wishlist'
        verbose_name_plural = 'Product Wishlists'
        unique_together     = ('user', 'product')
        ordering            = ['-created_at']
