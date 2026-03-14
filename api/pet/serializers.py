from rest_framework import serializers
from .models import PetProfile

class PetProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PetProfile
        fields = [
            "id",
            "user",
            "pet_name",
            "pet_type",
            "size",
            "weight",
            "weight_type",
            "date_of_birth",
            "vaccination_status",
            "vaccination_document",
            "vet_contact_number",
            "image",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ('id', 'user', 'created_at', 'updated_at')
