from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import FriendRequest, Friendship, UserBlock

User = get_user_model()

class NearbyUserSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    username = serializers.CharField(read_only=True)
    user_type = serializers.CharField(read_only=True)
    distance = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField()

    def get_distance(self, obj):
        distance = getattr(obj, 'distance', None)
        if distance is None:
            return None
        # If it's a GeoDjango Distance object, get miles
        if hasattr(distance, 'mi'):
            return float(distance.mi)
        # If it's already a float or something else convertible
        try:
            return float(distance)
        except (TypeError, ValueError):
            return None

    def get_profile_picture(self, obj):
        if hasattr(obj, 'profile') and obj.profile.profile_picture:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile.profile_picture.url)
            return obj.profile.profile_picture.url
        return None

class FriendRequestSerializer(serializers.ModelSerializer):
    sender_details = NearbyUserSerializer(source='sender', read_only=True)
    receiver_details = NearbyUserSerializer(source='receiver', read_only=True)

    class Meta:
        model = FriendRequest
        fields = ['id', 'sender', 'sender_details', 'receiver', 'receiver_details', 'status', 'created_at', 'updated_at']
        read_only_fields = ['id', 'sender', 'status', 'created_at', 'updated_at']

class FriendshipSerializer(serializers.ModelSerializer):
    friend_details = serializers.SerializerMethodField()

    class Meta:
        model = Friendship
        fields = ['id', 'user1', 'user2', 'friend_details', 'created_at']
        read_only_fields = ['id', 'user1', 'user2', 'created_at']

    def get_friend_details(self, obj):
        request = self.context.get('request')
        current_user = request.user if request else None
        
        friend = obj.user2 if obj.user1 == current_user else obj.user1
        return NearbyUserSerializer(friend, context={'request': request}).data

class UserBlockSerializer(serializers.ModelSerializer):
    blocked_user_details = NearbyUserSerializer(source='blocked_user', read_only=True)
    
    class Meta:
        model = UserBlock
        fields = ['id', 'blocker', 'blocked_user', 'blocked_user_details', 'created_at']
        read_only_fields = ['id', 'blocker', 'created_at']


class UserActionSerializer(serializers.Serializer):
    """Used for actions requiring just a user_id like unfriend, block, unblock"""
    user_id = serializers.UUIDField(required=True)

class CreateFriendRequestSerializer(serializers.Serializer):
    """Used specifically for creating friend requests via user ID"""
    receiver_id = serializers.UUIDField(required=True)

