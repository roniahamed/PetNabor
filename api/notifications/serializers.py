from rest_framework import serializers
from .models import NotificationSettings



class NotificationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationSettings
        fields = ['user', 'push_notifications', 'email_notifications', 'message_notifications', 'friend_request_notifications', 'like_notifications', 'comment_notifications', 'mention_notifications', 'meetup_notifications', 'vendor_post_notifications', 'product_share_notifications', 'product_interest_notifications', 'system_notifications', 'marketing_notifications', 'created_at', 'updated_at']
        read_only_fields = ['user', 'created_at', 'updated_at']
        
        