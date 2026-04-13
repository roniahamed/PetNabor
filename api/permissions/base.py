from rest_framework import permissions
from django.db.models import Q

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Generic: allow read to all, write only to the object's owner.
    Supports both `owner` and `user` as the ownership field.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if hasattr(obj, 'owner'):
            return obj.owner == request.user
        elif hasattr(obj, 'user'):
            return obj.user == request.user
        return False