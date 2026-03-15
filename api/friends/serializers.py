from django.db.models import Q
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
        distance = getattr(obj, "distance", None)
        if distance is None:
            return None
        if hasattr(distance, "mi"):
            return float(distance.mi)
        try:
            return float(distance)
        except (TypeError, ValueError):
            return None

    def get_profile_picture(self, obj):
        if hasattr(obj, "profile") and obj.profile.profile_picture:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.profile.profile_picture.url)
            return obj.profile.profile_picture.url
        return None


class FriendRequestSerializer(serializers.ModelSerializer):
    sender_details = NearbyUserSerializer(source="sender", read_only=True)
    receiver_details = NearbyUserSerializer(source="receiver", read_only=True)

    class Meta:
        model = FriendRequest
        fields = [
            "id",
            "sender",
            "sender_details",
            "receiver",
            "receiver_details",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "sender", "status", "created_at", "updated_at"]


class FriendshipSerializer(serializers.ModelSerializer):
    friend_details = serializers.SerializerMethodField()

    class Meta:
        model = Friendship
        fields = ["id", "sender", "receiver", "friend_details", "created_at"]
        read_only_fields = ["id", "sender", "receiver", "created_at"]

    def get_friend_details(self, obj):
        request = self.context.get("request")
        current_user = request.user if request else None

        friend = obj.receiver if obj.sender == current_user else obj.sender
        return NearbyUserSerializer(friend, context={"request": request}).data


class UserBlockSerializer(serializers.ModelSerializer):
    blocked_user_details = NearbyUserSerializer(source="blocked_user", read_only=True)

    class Meta:
        model = UserBlock
        fields = ["id", "blocker", "blocked_user", "blocked_user_details", "created_at"]
        read_only_fields = ["id", "blocker", "created_at"]


class UserActionSerializer(serializers.Serializer):
    """Used for actions requiring just a user_id like unfriend, block, unblock"""

    user_id = serializers.UUIDField(required=True)


class CreateFriendRequestSerializer(serializers.Serializer):
    """Used specifically for creating friend requests via user ID"""

    receiver_id = serializers.UUIDField(required=True)


class PublicUserSerializer(serializers.ModelSerializer):
    """
    Serializer for public user profiles.
    Hides sensitive data like email/phone and precise address.
    """

    bio = serializers.CharField(source="profile.bio", read_only=True)
    city = serializers.CharField(source="profile.city", read_only=True)
    state = serializers.CharField(source="profile.state", read_only=True)
    profile_picture = serializers.SerializerMethodField()
    cover_photo = serializers.SerializerMethodField()
    friendship_status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "username",
            "user_type",
            "bio",
            "city",
            "state",
            "profile_picture",
            "cover_photo",
            "friendship_status",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_profile_picture(self, obj):
        if hasattr(obj, "profile") and obj.profile.profile_picture:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.profile.profile_picture.url)
            return obj.profile.profile_picture.url
        return None

    def get_cover_photo(self, obj):
        if hasattr(obj, "profile") and obj.profile.cover_photo:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.profile.cover_photo.url)
            return obj.profile.cover_photo.url
        return None

    def get_friendship_status(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None

        current_user = request.user
        if current_user == obj:
            return "self"

        # Check existing friendship
        if Friendship.objects.filter(
            Q(sender=current_user, receiver=obj) | Q(sender=obj, receiver=current_user)
        ).exists():
            return "friends"

        # Check pending requests
        pending_out = FriendRequest.objects.filter(
            sender=current_user, receiver=obj, status="pending"
        ).exists()
        if pending_out:
            return "request_sent"

        pending_in = FriendRequest.objects.filter(
            sender=obj, receiver=current_user, status="pending"
        ).exists()
        if pending_in:
            return "request_received"

        return "none"
