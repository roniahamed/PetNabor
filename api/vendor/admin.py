from django.contrib import admin
from .models import Vendor

@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('id', 'business_name', 'user', 'city', 'state', 'created_at')
    search_fields = ('business_name', 'user__email', 'contact_number')
    list_filter = ('created_at',)
