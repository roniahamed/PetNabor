from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Categories, Brand, Product, ProductMedia, ProductEvent

@admin.register(Categories)
class CategoriesAdmin(ModelAdmin):
    list_display = ('name', 'slug', 'created_at')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Brand)
class BrandAdmin(ModelAdmin):
    list_display = ('name', 'slug', 'created_at')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ('name', 'vendor', 'category', 'price', 'is_active', 'created_at')
    search_fields = ('name', 'vendor__business_name', 'category__name')
    list_filter = ('is_active', 'category', 'created_at')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(ProductMedia)
class ProductMediaAdmin(ModelAdmin):
    list_display = ('product', 'type', 'is_primary', 'created_at')
    list_filter = ('type', 'is_primary')
    search_fields = ('product__name',)


@admin.register(ProductEvent)
class ProductEventAdmin(ModelAdmin):
    list_display = ('event_type', 'product', 'user', 'session_id', 'created_at')
    list_filter = ('event_type', 'created_at')
    search_fields = ('product__name', 'user__email', 'session_id')
    readonly_fields = ('created_at',)
