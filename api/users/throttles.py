"""
Custom throttle classes for PetNabor.

Problem with DRF's built-in throttles on AllowAny endpoints:
  - ScopedRateThrottle / AnonRateThrottle both key on the *client IP*.
  - If UserA hits the OTP limit from IP 1.2.3.4, UserB (same IP, e.g., same
    office/NAT) also gets blocked — even though they never sent a request.

Solution:
  - IdentityBasedOTPSendThrottle  → keys on email OR phone in the request body.
  - PerUserScopedThrottle          → for authenticated endpoints, keys on user PK
    (same as the default, but made explicit so we can subclass cleanly).
  - PerUserPostLikeThrottle        → high-frequency like/reaction limiter, per user,
    NOT per post — so one user can like 100 posts/minute without blocking others.
"""

import hashlib
import re
import time

from rest_framework.throttling import SimpleRateThrottle, ScopedRateThrottle


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _hash(value: str) -> str:
    """SHA-256 hex of a string — keeps cache keys short and safe."""
    return hashlib.sha256(value.encode()).hexdigest()


_UNIT_SECONDS = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
_RATE_RE = re.compile(
    r'^(?P<num>\d+)/(?P<mult>\d+)?(?P<unit>[smhd]|second|minute|hour|day)',
    re.IGNORECASE,
)


class _CustomParseMixin:
    """
    Mixin that overrides parse_rate to support formats like:
      '5/5minute'  → 5 requests per 300 seconds
      '200/minute' → 200 requests per 60 seconds  (standard)
      '40/hour'    → 40 requests per 3600 seconds (standard)
    """

    def parse_rate(self, rate):
        if rate is None:
            return (None, None)
        m = _RATE_RE.match(rate)
        if not m:
            # Fall back to DRF's default parser
            return super().parse_rate(rate)
        num = int(m.group('num'))
        mult = int(m.group('mult') or 1)
        unit = m.group('unit').lower()[0]  # first char: s/m/h/d
        duration = mult * _UNIT_SECONDS[unit]
        return (num, duration)

# ──────────────────────────────────────────────────────────────────────────────
# OTP Send — per identity (email or phone), NOT per IP
# ──────────────────────────────────────────────────────────────────────────────

class IdentityBasedOTPSendThrottle(_CustomParseMixin, SimpleRateThrottle):
    """
    Rate-limit OTP sending per unique identity (email or phone), not per IP.

    - Reads `email`, `phone`, or `email_or_phone` from the request body.
    - Falls back to IP only when no identity field is present (safety net).
    - Configured via DEFAULT_THROTTLE_RATES["otp_send"] in settings.
    """

    scope = "otp_send"

    def get_cache_key(self, request, view):
        # Try to extract the user's identity from the request body
        identity = (
            request.data.get("email")
            or request.data.get("phone")
            or request.data.get("email_or_phone")
        )

        if identity:
            # Key: throttle_otp_send_<hash-of-identity>
            return f"throttle_otp_send_{_hash(str(identity).strip().lower())}"

        # Fallback to IP — prevents total bypass when no identity is provided
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


# ──────────────────────────────────────────────────────────────────────────────
# OTP Verify — per identity (email or phone), NOT per IP
# ──────────────────────────────────────────────────────────────────────────────

class IdentityBasedOTPVerifyThrottle(_CustomParseMixin, SimpleRateThrottle):
    """
    Rate-limit OTP verification per unique identity (email or phone), not per IP.
    """

    scope = "otp_verify"

    def get_cache_key(self, request, view):
        identity = (
            request.data.get("email")
            or request.data.get("phone")
            or request.data.get("email_or_phone")
        )

        if identity:
            return f"throttle_otp_verify_{_hash(str(identity).strip().lower())}"

        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


# ──────────────────────────────────────────────────────────────────────────────
# Login — per identity (email_or_phone), NOT per IP
# ──────────────────────────────────────────────────────────────────────────────

class IdentityBasedLoginThrottle(_CustomParseMixin, SimpleRateThrottle):
    """
    Rate-limit login attempts per account (email/phone), not per IP.
    Prevents one attacker from locking out all users on a shared IP.
    """

    scope = "auth_login"

    def get_cache_key(self, request, view):
        identity = (
            request.data.get("email_or_phone")
            or request.data.get("email")
            or request.data.get("phone")
        )

        if identity:
            return f"throttle_auth_login_{_hash(str(identity).strip().lower())}"

        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


# ──────────────────────────────────────────────────────────────────────────────
# Post / Blog Reaction — per authenticated user, NOT per post and NOT per IP
# ──────────────────────────────────────────────────────────────────────────────

class PerUserPostLikeThrottle(_CustomParseMixin, SimpleRateThrottle):
    """
    Rate-limit post/blog like & reaction actions per *user*, not per post.

    This means:
      - User A can like up to N posts per minute regardless of which posts.
      - User B's actions are completely independent of User A.
      - Configured via DEFAULT_THROTTLE_RATES["post_like"] in settings.
    """

    scope = "post_like"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return f"throttle_post_like_user_{request.user.pk}"

        # Unauthenticated access: fall back to IP (should rarely happen on
        # these endpoints since they require IsAuthenticated)
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


# ──────────────────────────────────────────────────────────────────────────────
# Post Save — per authenticated user
# ──────────────────────────────────────────────────────────────────────────────

class PerUserPostSaveThrottle(_CustomParseMixin, SimpleRateThrottle):
    """Rate-limit post save/bookmark actions per user."""

    scope = "post_save"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return f"throttle_post_save_user_{request.user.pk}"

        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


# ──────────────────────────────────────────────────────────────────────────────
# Post Comment — per authenticated user
# ──────────────────────────────────────────────────────────────────────────────

class PerUserPostCommentThrottle(_CustomParseMixin, SimpleRateThrottle):
    """Rate-limit comment creation per user."""

    scope = "post_comment"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return f"throttle_post_comment_user_{request.user.pk}"

        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


# ──────────────────────────────────────────────────────────────────────────────
# Messaging Send — per authenticated user
# ──────────────────────────────────────────────────────────────────────────────

class PerUserMessagingThrottle(_CustomParseMixin, SimpleRateThrottle):
    """Rate-limit message sending per user."""

    scope = "messaging_send"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return f"throttle_messaging_user_{request.user.pk}"

        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }
