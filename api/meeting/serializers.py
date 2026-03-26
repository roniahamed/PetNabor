from rest_framework import serializers
from .models import Meeting, MeetingFeedback
from api.users.serializers import Profile_Read
from django.contrib.auth import get_user_model

User = get_user_model()

class CustomUserSerializer(serializers.ModelSerializer):
    profile = Profile_Read(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'profile']

class MeetingSerializer(serializers.ModelSerializer):
    sender = CustomUserSerializer(read_only=True)
    receiver_details = CustomUserSerializer(source='receiver', read_only=True)
    # Exposing receiver ID field for creation but with a different name or write-only
    receiver_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source='receiver', write_only=True
    )

    class Meta:
        model = Meeting
        fields = [
            'id', 'sender', 'receiver_id', 'receiver_details', 
            'visitor_name', 'visitor_phone', 'visit_date', 'visit_time', 'reason', 
            'address_street', 'city', 'state', 'zipcode', 'message', 
            'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'sender', 'status', 'created_at', 'updated_at']


class MeetingFeedbackSerializer(serializers.ModelSerializer):
    reviewer = CustomUserSerializer(read_only=True)
    reviewee_details = CustomUserSerializer(source='reviewee', read_only=True)

    class Meta:
        model = MeetingFeedback
        fields = [
            'id', 'meeting', 'reviewer', 'reviewee', 'reviewee_details', 
            'rating', 'feedback_text', 'is_public', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'reviewer', 'created_at', 'updated_at']

