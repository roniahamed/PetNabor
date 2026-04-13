from rest_framework import serializers
from .models import Categories, Brand, Product, ProductMedia


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Categories
        fields = ['id', 'name', 'slug', 'image', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']

class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ['id', 'name', 'slug', 'image', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']
        
class ProductMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductMedia
        fields = ['id', 'product', 'media_file', 'type', 'thumbnail', 'is_primary', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class ProductSerializer(serializers.ModelSerializer):
        media = ProductMediaSerializer(many=True, read_only=True)
    
        class Meta:
            model = Product
            fields = ['id', 'vendor', 'user', 'slug', 'name', 'description', 'price', 'category', 'brand', 'external_product_url', 'is_active', 'created_at', 'updated_at', 'media']
            read_only_fields = ['id', 'slug', 'created_at', 'updated_at']