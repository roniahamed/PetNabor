from rest_framework import serializers
from .models import SiteSettings

class SiteSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteSettings
        fields = [
            'site_name',
            'site_logo',
            'contact_email',
            'maintenance_mode',
            'allow_vendor_registration',
            'allow_user_registration',
            'featured_category',
            'products_per_page',
        ]
