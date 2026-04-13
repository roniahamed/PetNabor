from rest_framework import permissions
from django.db.models import Q




class IsStaffOrReadOnly(permissions.BasePermission):
    """
    Generic: allow read to all, write only to staff users.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff




class IsVendorOrReadOnly(permissions.BasePermission):
    """
    Generic: allow read to all, write only to the product's vendor.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.vendor == request.user.vendor