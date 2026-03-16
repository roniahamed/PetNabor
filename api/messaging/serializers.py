"""
Messaging serializers.

DRY, clean, minimal — fields named exactly as model fields.
No business logic here; all validation lives in services.py.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import ChatThread, Message, MessageTypes, ThreadParticipant, ThreadTypes

User = get_user_model()


# ──────────────────────────────────────────────
# Minimal nested user representation
# ──────────────────────────────────────────────


class ParticipantUserSerializer(serializers.ModelSerializer):
    """Lightweight user info for embedding inside thread/message responses."""

    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "avatar", "is_online"]
        read_only_fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "avatar",
            "is_online",
        ]

    def get_avatar(self, user):
        profile = getattr(user, "profile", None)
        if profile and profile.profile_picture:
            request = self.context.get("request")
            url = profile.profile_picture.url
            return request.build_absolute_uri(url) if request else url
        return None


# ──────────────────────────────────────────────
# ThreadParticipant
# ──────────────────────────────────────────────


class ThreadParticipantSerializer(serializers.ModelSerializer):
    user = ParticipantUserSerializer(read_only=True)

    class Meta:
        model = ThreadParticipant
        fields = ["id", "user", "role", "is_muted", "joined_at", "left_at"]
        read_only_fields = [
            "id",
            "user",
            "role",
            "is_muted",
            "joined_at",
            "left_at",
        ]


# ──────────────────────────────────────────────
# Message
# ──────────────────────────────────────────────


class ReplyPreviewSerializer(serializers.ModelSerializer):
    """Compact representation of the replied-to message."""

    sender = ParticipantUserSerializer(read_only=True)

    class Meta:
        model = Message
        fields = ["id", "sender", "message_type", "text_content", "media_url"]
        read_only_fields = [
            "id",
            "sender",
            "message_type",
            "text_content",
            "media_url",
        ]


class MessageSerializer(serializers.ModelSerializer):
    sender = ParticipantUserSerializer(read_only=True)
    reply_to = ReplyPreviewSerializer(read_only=True)

    class Meta:
        model = Message
        fields = [
            "id",
            "thread",
            "sender",
            "message_type",
            "text_content",
            "media_url",
            "reply_to",
            "is_read",
            "is_edited",
            "is_deleted_for_everyone",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "sender",
            "thread",
            "is_read",
            "is_edited",
            "is_deleted_for_everyone",
            "created_at",
            "updated_at",
        ]


class SendMessageSerializer(serializers.Serializer):
    """Input serializer for creating a new message."""

    message_type = serializers.ChoiceField(
        choices=MessageTypes.choices,
        default=MessageTypes.TEXT,
    )
    text_content = serializers.CharField(
        max_length=Message.MAX_TEXT_LENGTH,
        required=False,
        allow_blank=False,
    )
    media_url = serializers.URLField(max_length=512, required=False)
    reply_to_id = serializers.UUIDField(required=False)

    def validate(self, data):
        msg_type = data.get("message_type", MessageTypes.TEXT)
        if msg_type == MessageTypes.TEXT and not data.get("text_content"):
            raise serializers.ValidationError(
                {"text_content": "Required for TEXT messages."}
            )
        if msg_type != MessageTypes.TEXT and not data.get("media_url"):
            raise serializers.ValidationError(
                {"media_url": "Required for non-TEXT messages."}
            )
        return data


# ──────────────────────────────────────────────
# ChatThread
# ──────────────────────────────────────────────


class ChatThreadSerializer(serializers.ModelSerializer):
    """
    Full thread serializer for retrieve/list.
    Participants come from the prefetched `active_participants` attr set by the service.
    last_message is the first item from `recent_messages` if present.
    """

    participants = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    created_by = ParticipantUserSerializer(read_only=True)

    class Meta:
        model = ChatThread
        fields = [
            "id",
            "thread_type",
            "name",
            "description",
            "avatar_url",
            "created_by",
            "participants",
            "last_message",
            "last_message_text",
            "last_message_timestamp",
            "created_at",
            "updated_at",
        ]

    def get_participants(self, thread):
        # Use prefetched attr when available (avoids extra query)
        members = getattr(thread, "active_participants", None)
        if members is None:
            members = thread.participants.filter(left_at__isnull=True).select_related(
                "user__profile"
            )
        return ThreadParticipantSerializer(
            members, many=True, context=self.context
        ).data

    def get_last_message(self, thread):
        recent = getattr(thread, "recent_messages", None)
        if recent:
            return MessageSerializer(recent[0], context=self.context).data
        return None


class CreateDirectThreadSerializer(serializers.Serializer):
    """Input serializer for starting a DIRECT chat."""

    recipient_id = serializers.UUIDField()


class CreateGroupThreadSerializer(serializers.Serializer):
    """Input serializer for creating a GROUP thread."""

    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    avatar_url = serializers.URLField(required=False)
    member_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
    )
class BulkDeleteMessagesSerializer(serializers.Serializer):
    """Input for bulk message deletion."""

    message_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=100,
    )
