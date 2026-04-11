import uuid
import os
from django.db import models
from django.conf import settings
from django.contrib.gis.db import models as gis_models

def vendor_logo_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"vendor_{uuid.uuid4()}.{ext}"
    return os.path.join('vendors/logos/', filename)

class Vendor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='vendor_profiles')
    
    logo = models.ImageField(upload_to=vendor_logo_path, null=True, blank=True)
    business_name = models.CharField(max_length=255)
    descriptions = models.TextField(blank=True, null=True)
    
    address_street = models.CharField(max_length=255, null=True, blank=True)
    apartment = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    zipcode = models.CharField(max_length=20, null=True, blank=True)
    location_point = gis_models.PointField(srid=4326, null=True, blank=True)
    
    plan = models.CharField(max_length=100, null=True, blank=True)
    contact_number = models.CharField(max_length=20, null=True, blank=True)
    whatsapp_number = models.CharField(max_length=20, null=True, blank=True)
    website_link = models.URLField(max_length=500, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.business_name
