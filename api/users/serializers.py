from rest_framework import serializers

class FirebaseTokenSerializer(serializers.Serializer):
    id_token = serializers.CharField(required=True, help_text="Firebase ID Token")
    
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    user_type = serializers.CharField(required=False, default='patnabor')
    agree_to_terms_and_conditions = serializers.BooleanField(required=False, default=False)