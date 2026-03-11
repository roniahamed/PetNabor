from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class FirebaseTokenSerializer(serializers.Serializer):
    id_token = serializers.CharField(required=True, help_text="Firebase ID Token")
    
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    user_type = serializers.CharField(required=False, default='patnabor')
    agree_to_terms_and_conditions = serializers.BooleanField(required=False, default=False)
    
    
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'phone', 'first_name', 'last_name', 'user_type', 'is_verified', 'is_active', 'is_staff', 'is_superuser', 'created_at', 'agree_to_terms_and_conditions', 'is_patpal', 'is_online', 'last_active', 'firebase_uid', 'username', 'updated_at']
        read_only_fields = ['id', 'is_verified', 'is_active', 'is_staff', 'is_superuser', 'created_at', 'email', 'phone', 'updated_at', 'firebase_uid', 'username', 'last_seen',]
        
        