from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import ProductWishlist

@admin.register(ProductWishlist)
class ProductWishlistAdmin(ModelAdmin):
    list_display = ('product', 'user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('product__name', 'user__email', 'user__first_name')
    readonly_fields = ('created_at',)
