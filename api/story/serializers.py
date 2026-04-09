"""
Serializers for the Story feature.

Key design choices:
- `is_viewed` and `user_reaction` are read from prefetched attributes (zero extra DB hits).
- `StoryCreateSerializer` validates that media_type matches the supplied fields.
- `StoryAuthorSerializer` is a lightweight embed — avoids N+1 from full User serializer.
"""

from rest_framework import serializers

from api.users.models import User
from .models import Story, StoryMediaTypeChoices, StoryReaction, StoryReply, StoryView





# ──────────────────────────────────────────────
# Shared / Nested
# ──────────────────────────────────────────────


class StoryAuthorSerializer(serializers.ModelSerializer):
    """Lightweight user embed — profile_picture sourced from related Profile."""

    profile_picture = serializers.ImageField(
        source="profile.profile_picture", read_only=True
    )

    class Meta:
        model = User
        fields = ["id", "first_name", "last_name", "username", "profile_picture"]


# ──────────────────────────────────────────────
# Story Write
# ──────────────────────────────────────────────


class StoryCreateSerializer(serializers.ModelSerializer):
    """
    Input serializer for story creation.
    Validates that the supplied fields match the chosen media_type:
    - TEXT  → text_content required, media_url forbidden
    - IMAGE/VIDEO → media_url required, text_content ignored
    """

    class Meta:
        model = Story
        fields = [
            "media_type",
            "media",
            "text_content",
            "bg_color",
            "privacy",
        ]

    def validate(self, attrs: dict) -> dict:
        media_type = attrs.get("media_type", StoryMediaTypeChoices.TEXT)

        if media_type == StoryMediaTypeChoices.TEXT:
            if not attrs.get("text_content"):
                raise serializers.ValidationError(
                    {"text_content": "text_content is required for TEXT stories."}
                )
            # Remove irrelevant field
            attrs.pop("media", None)

        else:  # IMAGE or VIDEO
            if not attrs.get("media"):
                raise serializers.ValidationError(
                    {
                        "media": (
                            f"media file is required for {media_type} stories."
                        )
                    }
                )

        return attrs


# ──────────────────────────────────────────────
# Story Read
# ──────────────────────────────────────────────


class StoryListSerializer(serializers.ModelSerializer):
    """
    Optimised for feed/list views.

    `is_viewed`    → from prefetched StoryView; no extra DB hit.
    `user_reaction`→ from prefetched `user_reactions` attribute; no extra DB hit.
    """

    author = StoryAuthorSerializer(read_only=True)
    is_viewed = serializers.SerializerMethodField()
    user_reaction = serializers.SerializerMethodField()

    class Meta:
        model = Story
        fields = [
            "id",
            "author",
            "media_type",
            "media",
            "text_content",
            "bg_color",
            "privacy",
            "views_count",
            "is_viewed",
            "user_reaction",
            "expires_at",
            "created_at",
        ]

    def get_is_viewed(self, obj) -> bool:
        """
        Uses the `has_unseen` annotation (added by _annotate_story_queryset)
        when present. Falls back to a DB query if annotation is missing.
        """
        # has_unseen=True means NOT viewed yet; has_unseen=False means viewed
        has_unseen = getattr(obj, "has_unseen", None)
        if has_unseen is not None:
            return not has_unseen

        # Fallback (e.g. single-object retrieve without annotation)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.views.filter(viewer=request.user).exists()
        return False

    def get_user_reaction(self, obj) -> str | None:
        """Returns the requesting user's reaction type, or None."""
        user_reactions = getattr(obj, "user_reactions", None)
        if user_reactions is not None:
            return user_reactions[0].reaction_type if user_reactions else None

        request = self.context.get("request")
        if request and request.user.is_authenticated:
            reaction = obj.reactions.filter(user=request.user).first()
            return reaction.reaction_type if reaction else None
        return None


class StoryDetailSerializer(StoryListSerializer):
    """
    Single-story detail view — adds reaction and reply counts.
    Counts are computed from the DB (only used on retrieve, not feed lists).
    """

    reactions_count = serializers.SerializerMethodField()
    replies_count = serializers.SerializerMethodField()

    class Meta(StoryListSerializer.Meta):
        fields = StoryListSerializer.Meta.fields + [
            "reactions_count",
            "replies_count",
        ]

    def get_reactions_count(self, obj) -> int:
        # On retrieve we call .count() once; acceptable for single-object views
        return obj.reactions.count()

    def get_replies_count(self, obj) -> int:
        return obj.replies.count()


# ──────────────────────────────────────────────
# Story View (Viewers list)
# ──────────────────────────────────────────────


class StoryViewSerializer(serializers.ModelSerializer):
    viewer = StoryAuthorSerializer(read_only=True)

    class Meta:
        model = StoryView
        fields = ["id", "viewer", "viewed_at"]


# ──────────────────────────────────────────────
# Story Reaction
# ──────────────────────────────────────────────


class StoryReactionSerializer(serializers.ModelSerializer):
    user = StoryAuthorSerializer(read_only=True)

    class Meta:
        model = StoryReaction
        fields = ["id", "user", "reaction_type", "created_at"]
        read_only_fields = ["id", "user", "created_at"]


class StoryReactionCreateSerializer(serializers.Serializer):
    """Simple input-only serializer for reaction type validation."""

    reaction_type = serializers.ChoiceField(
        choices=StoryReaction._meta.get_field("reaction_type").choices
    )


# ──────────────────────────────────────────────
# Story Reply
# ──────────────────────────────────────────────


class StoryReplySerializer(serializers.ModelSerializer):
    user = StoryAuthorSerializer(read_only=True)

    class Meta:
        model = StoryReply
        fields = ["id", "user", "reply_text", "created_at"]
        read_only_fields = ["id", "user", "created_at"]

    def validate_reply_text(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Reply text cannot be blank.")
        return value


# ──────────────────────────────────────────────
# Story Feed — Grouped
# ──────────────────────────────────────────────


class StoryUserGroupSerializer(serializers.Serializer):
    """Grouped feed entry: one user with all their active stories."""

    user = StoryAuthorSerializer(read_only=True)
    has_unseen = serializers.BooleanField()
    latest_story_at = serializers.DateTimeField()
    stories = StoryListSerializer(many=True, read_only=True)
