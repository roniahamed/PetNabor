"""
Authentication middleware.

UpdateLastActiveMiddleware: Tracks user activity timestamps.
VerificationEnforcementMiddleware: Blocks unverified users from protected endpoints.
"""

import logging

from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)

# Endpoints that unverified users can access
AUTH_WHITELISTED_PATHS = (
    "/api/users/signup/",
    "/api/users/login/",
    "/api/users/login/firebase/",
    "/api/users/verify-phone/",
    "/api/users/verify-email/",
    "/api/users/resend-phone-otp/",
    "/api/users/resend-email-otp/",
    "/api/users/password-reset/",
    "/api/users/token/refresh/",
    "/admin/",
)

# Throttle last_active DB writes: at most one write per user every 60 seconds.
LAST_ACTIVE_THROTTLE_S = 60


class UpdateLastActiveMiddleware(MiddlewareMixin):
    """
    Update the authenticated user's last_active timestamp on every request,
    throttled to one DB write per LAST_ACTIVE_THROTTLE_S seconds per user.

    is_online is NOT stored directly; use user.currently_online property which
    computes it from last_active (< 5 min ago → online).
    """

    def process_request(self, request):
        if not request.user.is_authenticated:
            try:
                header = JWTAuthentication().get_header(request)
                if header:
                    raw_token = JWTAuthentication().get_raw_token(header)
                    validated_token = JWTAuthentication().get_validated_token(raw_token)
                    user = JWTAuthentication().get_user(validated_token)
                    request.user = user
            except Exception:
                pass

        if request.user.is_authenticated:
            cache_key = f"last_active_ts_{request.user.id}"
            if not cache.get(cache_key):
                # Throttled write: update only last_active (no is_online field)
                User = get_user_model()
                User.objects.filter(id=request.user.id).update(
                    last_active=timezone.now()
                )
                cache.set(cache_key, True, LAST_ACTIVE_THROTTLE_S)

        return None



class VerificationEnforcementMiddleware(MiddlewareMixin):
    """
    Block unverified users from accessing protected API endpoints.

    Returns 403 Forbidden with a clean JSON response for unverified users.
    Auth-related endpoints are whitelisted so users can complete verification.
    """

    def process_request(self, request):
        # Skip whitelisted paths
        path = request.path
        if any(path.startswith(whitelisted) for whitelisted in AUTH_WHITELISTED_PATHS):
            return None

        # Skip non-authenticated requests (DRF will handle permission denial)
        if not request.user.is_authenticated:
            return None

        # Block unverified users
        if not request.user.is_verified:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Your account is not verified. Please verify your email or phone number.",
                    "error_code": "account_not_verified",
                },
                status=403,
            )

        return None