"""
Custom permission classes for the Story app.

Isolating permission logic here keeps views lean and makes
individual rules easy to test and compose.
"""

from django.db.models import Q
from rest_framework import permissions

from api.friends.models import Friendship
from .models import StoryPrivacyChoices


class IsStoryAuthor(permissions.BasePermission):
    """
    Only the story's author may modify or delete it.
    Safe methods (GET/HEAD/OPTIONS) pass through.
    """

    message = "You do not have permission to modify this story."

    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.author == request.user


class CanViewStory(permissions.BasePermission):
    """
    Enforces Story.privacy levels:
    - PUBLIC       → any authenticated user can view.
    - FRIENDS_ONLY → only the author and mutual friends can view.

    The friendship check hits the DB once via a single Q() query;
    result is NOT cached here — call sites should avoid calling this
    in a loop without prefetching.
    """

    message = "This story is not available to you."

    def has_object_permission(self, request, view, obj) -> bool:
        # Author always sees their own story (even expired, for delete)
        if obj.author == request.user:
            return True

        if obj.privacy == StoryPrivacyChoices.PUBLIC:
            return True

        if obj.privacy == StoryPrivacyChoices.FRIENDS_ONLY:
            return Friendship.objects.filter(
                Q(sender=obj.author, receiver=request.user)
                | Q(sender=request.user, receiver=obj.author)
            ).exists()

        return False
