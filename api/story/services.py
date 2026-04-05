"""
Business logic for the Story feature.

Service layer principles applied:
- All DB mutations inside @transaction.atomic
- F() expressions for counter updates (race-condition safe)
- No view logic here — views call services only
- Notifications dispatched async via existing send_notification()
"""

import logging
from typing import Tuple

from django.conf import settings
from django.db import transaction
from django.db.models import Exists, F, OuterRef, Prefetch, Q, QuerySet
from django.utils import timezone

from api.friends.models import Friendship
from api.users.models import User
from .models import (
    Story,
    StoryMediaTypeChoices,
    StoryPrivacyChoices,
    StoryReaction,
    StoryReply,
    StoryView,
)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

STORY_EXPIRY_HOURS: int = getattr(settings, "STORY_EXPIRY_HOURS", 24)


# ──────────────────────────────────────────────────────────────────────────────
# Story Service
# ──────────────────────────────────────────────────────────────────────────────


class StoryService:
    """Handles story creation, deletion, and per-user retrieval."""

    @staticmethod
    @transaction.atomic
    def publish_story(user: User, data: dict) -> Story:
        """
        Creates a new story and sets the expiry timestamp.
        expires_at is always derived server-side to prevent client manipulation.
        """
        from datetime import timedelta

        expiry_delta = timedelta(hours=STORY_EXPIRY_HOURS)
        story = Story.objects.create(
            author=user,
            media_type=data["media_type"],
            media=data.get("media"),
            text_content=data.get("text_content"),
            bg_color=data.get("bg_color"),
            privacy=data.get("privacy", StoryPrivacyChoices.PUBLIC),
            expires_at=timezone.now() + expiry_delta,
        )

        if story.media_type == StoryMediaTypeChoices.IMAGE and story.media:
            from .tasks import process_story_media_task

            process_story_media_task.delay(str(story.id))

        return story

    @staticmethod
    @transaction.atomic
    def delete_story(story: Story, requesting_user: User) -> None:
        """
        Hard-deletes the story. Raises PermissionError if caller isn't the author.
        Stories expire naturally, so soft-delete adds no value here.
        """
        if story.author_id != requesting_user.id:
            raise PermissionError("You do not have permission to delete this story.")
        story.delete()

    @staticmethod
    def get_active_queryset() -> QuerySet:
        """Base queryset: only non-expired stories."""
        return Story.objects.filter(expires_at__gt=timezone.now())

    @staticmethod
    def get_active_stories_for_user(
        target_user: User, requesting_user: User
    ) -> QuerySet:
        """
        Returns target_user's active stories visible to requesting_user.
        - Author sees all their own active stories.
        - If blocked in either direction, returns empty queryset.
        - Friends see PUBLIC + FRIENDS_ONLY stories.
        - Strangers see only PUBLIC stories.
        """
        qs = StoryService.get_active_queryset().filter(author=target_user)

        if target_user == requesting_user:
            # Owner sees all their own stories
            pass
        else:
            # Block check: if blocked in either direction, no stories visible
            from api.friends.services import is_blocked as _is_blocked
            if _is_blocked(requesting_user, target_user):
                return Story.objects.none()

            is_friend = Friendship.objects.filter(
                Q(sender=target_user, receiver=requesting_user)
                | Q(sender=requesting_user, receiver=target_user)
            ).exists()

            if not is_friend:
                qs = qs.filter(privacy=StoryPrivacyChoices.PUBLIC)
            # friends see both PUBLIC and FRIENDS_ONLY (no filter needed)

        return _annotate_story_queryset(qs, requesting_user)


# ──────────────────────────────────────────────────────────────────────────────
# Story Feed Service
# ──────────────────────────────────────────────────────────────────────────────


class StoryFeedService:
    """
    Builds the personalised story feed for the authenticated user.

    Feed algorithm (SQL-native, no ML needed):
    1. Include stories from: self + friends (mutual Friendship rows).
    2. Exclude expired stories.
    3. Order by:
       a. Has unseen story from this author? (unseen-first) — annotated boolean DESC
       b. Most recent story created_at DESC (recency)

    This means users with fresh, unread stories bubble to the top.
    No extra query per story — unseen flag comes from a single Exists subquery.
    """

    @staticmethod
    def get_story_feed(user: User) -> QuerySet:
        from api.friends.models import UserBlock

        friend_pair_ids = Friendship.objects.filter(
            Q(sender=user) | Q(receiver=user)
        ).values_list("sender_id", "receiver_id")

        # Flatten both sides of the friendship into one set (including self)
        visible_author_ids: set = {user.id}
        for sender_id, receiver_id in friend_pair_ids:
            visible_author_ids.add(sender_id)
            visible_author_ids.add(receiver_id)

        # Collect blocked user IDs (both directions) to exclude
        flat_blocked: set = set()
        for pair in UserBlock.objects.filter(
            Q(blocker=user) | Q(blocked_user=user)
        ).values_list("blocker_id", "blocked_user_id"):
            flat_blocked.update(pair)
        flat_blocked.discard(user.id)  # never exclude self

        # Base: active stories from visible authors, excluding blocked users
        qs = (
            StoryService.get_active_queryset()
            .filter(author_id__in=visible_author_ids)
            .exclude(author_id__in=flat_blocked)
            .exclude(
                # Exclude FRIENDS_ONLY stories from people who are NOT friends
                # (self is already excluded above via author_id check)
                ~Q(author=user) & Q(privacy=StoryPrivacyChoices.FRIENDS_ONLY) &
                ~Q(
                    author_id__in=Friendship.objects.filter(
                        Q(sender=user) | Q(receiver=user)
                    ).values_list("sender_id", flat=True)
                ) &
                ~Q(
                    author_id__in=Friendship.objects.filter(
                        Q(sender=user) | Q(receiver=user)
                    ).values_list("receiver_id", flat=True)
                )
            )
        )

        return _annotate_story_queryset(qs, user).order_by(
            "-has_unseen",   # Unseen stories float to top
            "-created_at",   # Then by recency
        )


# ──────────────────────────────────────────────────────────────────────────────
# Story View Service
# ──────────────────────────────────────────────────────────────────────────────


class StoryViewService:
    """Tracks who viewed a story and exposes the viewers list to the author."""

    @staticmethod
    @transaction.atomic
    def mark_as_viewed(story: Story, viewer: User) -> bool:
        """
        Records a single unique view per (story, viewer) pair.
        Increments views_count via F() only on the first view (race-safe).
        Returns True if this was a new view, False if already viewed.
        """
        _, created = StoryView.objects.get_or_create(
            story=story,
            viewer=viewer,
        )
        if created:
            Story.objects.filter(id=story.id).update(
                views_count=F("views_count") + 1
            )
        return created

    @staticmethod
    def get_story_viewers(story: Story, requesting_user: User) -> QuerySet:
        """
        Returns the viewers list. Only the story's author may access this.
        Raises PermissionError for any other caller.
        """
        if story.author_id != requesting_user.id:
            raise PermissionError("Only the story author can view the viewers list.")

        return (
            StoryView.objects.filter(story=story)
            .select_related("viewer", "viewer__profile")
            .order_by("-viewed_at")
        )


# ──────────────────────────────────────────────────────────────────────────────
# Story Interaction Service
# ──────────────────────────────────────────────────────────────────────────────


class StoryInteractionService:
    """Handles reactions and replies to stories."""

    @staticmethod
    @transaction.atomic
    def react_to_story(
        story: Story, user: User, reaction_type: str
    ) -> Tuple[StoryReaction, bool]:
        """
        Upserts a reaction on a story.
        - New reaction → created=True
        - Changed reaction type → updates in place, created=False
        Returns (reaction_obj, created).
        """
        reaction, created = StoryReaction.objects.get_or_create(
            story=story,
            user=user,
            defaults={"reaction_type": reaction_type},
        )
        if not created and reaction.reaction_type != reaction_type:
            reaction.reaction_type = reaction_type
            reaction.save(update_fields=["reaction_type"])

        # Notify story author of the reaction (non-blocking via Celery)
        if created and story.author_id != user.id:
            _notify_story_author_of_reaction(story, user)

        return reaction, created

    @staticmethod
    @transaction.atomic
    def remove_reaction(story: Story, user: User) -> bool:
        """
        Removes the user's reaction from a story.
        Returns True if a reaction was deleted, False if none existed.
        """
        deleted_count, _ = StoryReaction.objects.filter(
            story=story, user=user
        ).delete()
        return deleted_count > 0

    @staticmethod
    @transaction.atomic
    def reply_to_story(story: Story, user: User, reply_text: str) -> StoryReply:
        """
        Creates a text reply to a story and notifies the story's author.
        """
        reply = StoryReply.objects.create(
            story=story,
            user=user,
            reply_text=reply_text,
        )

        # Notify story author of the reply (non-blocking)
        if story.author_id != user.id:
            _notify_story_author_of_reply(story, user)

        return reply

    @staticmethod
    def get_story_replies(story: Story, requesting_user: User) -> QuerySet:
        """
        Returns replies for a story.
        Only the story author or the replier can see each reply.
        For simplicity, author sees all; others only see their own.
        """
        qs = StoryReply.objects.filter(story=story).select_related(
            "user", "user__profile"
        )
        if story.author_id == requesting_user.id:
            return qs
        return qs.filter(user=requesting_user)


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers (not part of the public service API)
# ──────────────────────────────────────────────────────────────────────────────


def _annotate_story_queryset(qs: QuerySet, requesting_user: User) -> QuerySet:
    """
    Applies standard join/prefetch optimisations and the `has_unseen` annotation.

    has_unseen: True when requesting_user has NOT viewed a story yet.
    Used by the feed ordering with zero extra queries (single Exists subquery).
    """
    already_viewed_subquery = StoryView.objects.filter(
        story=OuterRef("pk"),
        viewer=requesting_user,
    )
    return (
        qs.select_related("author", "author__profile")
        .prefetch_related(
            # Prefetch only the requesting user's reaction to avoid N+1
            Prefetch(
                "reactions",
                queryset=StoryReaction.objects.filter(user=requesting_user),
                to_attr="user_reactions",
            )
        )
        .annotate(has_unseen=~Exists(already_viewed_subquery))
    )


def _notify_story_author_of_reaction(story: Story, reactor: User) -> None:
    """Fires a non-blocking push notification to the story author."""
    try:
        from api.notifications.services import send_notification
        from api.notifications.models import NotificationTypes

        send_notification(
            title="Story Reaction",
            body=f"{reactor.first_name or reactor.username} reacted to your story.",
            user_id=story.author_id,
            notification_type=NotificationTypes.STORY_LIKE,
            data={"story_id": str(story.id)},
        )
    except Exception:
        logger.exception(
            "Failed to send story reaction notification for story %s", story.id
        )


def _notify_story_author_of_reply(story: Story, replier: User) -> None:
    """Fires a non-blocking push notification to the story author."""
    try:
        from api.notifications.services import send_notification
        from api.notifications.models import NotificationTypes

        send_notification(
            title="Story Reply",
            body=f"{replier.first_name or replier.username} replied to your story.",
            user_id=story.author_id,
            notification_type=NotificationTypes.STORY_COMMENT,
            data={"story_id": str(story.id)},
        )
    except Exception:
        logger.exception(
            "Failed to send story reply notification for story %s", story.id
        )
