from rest_framework import permissions

class IsVendorUser(permissions.BasePermission):
    """
    Allows access only to users with user_type 'vendor' or admins.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        # Allow read-only for anyone so users can see vendor profiles
        if request.method in permissions.SAFE_METHODS:
            return True
            
        # For creation/editing, must be a vendor or admin
        return request.user.user_type == 'vendor' or request.user.user_type == 'admin' or request.user.is_staff

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of a vendor profile to edit or delete it.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user == request.user or request.user.is_staff
