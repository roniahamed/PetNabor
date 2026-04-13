from rest_framework import serializers
from django.contrib.gis.geos import Point
from .models import Vendor

class VendorSerializer(serializers.ModelSerializer):
    longitude = serializers.FloatField(write_only=True, required=False)
    latitude = serializers.FloatField(write_only=True, required=False)
    
    class Meta:
        model = Vendor
        fields = [
            'id', 'user', 'logo', 'business_name', 'descriptions',
            'address_street', 'apartment', 'city', 'state', 'zipcode',
            'location_point', 'plan', 'contact_number', 'whatsapp_number',
            'website_link', 'longitude', 'latitude', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'location_point', 'created_at', 'updated_at']
        
    def create(self, validated_data):
        longitude = validated_data.pop('longitude', None)
        latitude = validated_data.pop('latitude', None)
        if longitude is not None and latitude is not None:
            validated_data['location_point'] = Point(longitude, latitude, srid=4326)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        longitude = validated_data.pop('longitude', None)
        latitude = validated_data.pop('latitude', None)
        if longitude is not None and latitude is not None:
            validated_data['location_point'] = Point(longitude, latitude, srid=4326)
        return super().update(instance, validated_data)
