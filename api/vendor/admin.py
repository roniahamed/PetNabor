from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Vendor, VendorPlan, VendorSubscription

@admin.register(Vendor)
class VendorAdmin(ModelAdmin):
    list_display = ('id', 'business_name', 'user', 'plan', 'city', 'state', 'created_at')
    search_fields = ('business_name', 'user__email', 'contact_number')
    list_filter = ('created_at', 'plan')

@admin.register(VendorPlan)
class VendorPlanAdmin(ModelAdmin):
    list_display = ('name', 'price', 'max_products', 'has_category_top_slot', 'has_advanced_analytics')
    search_fields = ('name',)
    list_filter = ('price', 'max_products')

@admin.register(VendorSubscription)
class VendorSubscriptionAdmin(ModelAdmin):
    list_display = ('vendor', 'plan', 'status', 'started_at', 'expires_at')
    search_fields = ('vendor__business_name', 'plan__name')
    list_filter = ('status', 'started_at')
