from rest_framework import serializers
from .models import VerificationConfig

class VerificationConfigSerializer(serializers.ModelSerializer):
    """Serializer to expose verification price and active status."""

    class Meta:
        model = VerificationConfig
        fields = ["verification_price", "is_active"]
