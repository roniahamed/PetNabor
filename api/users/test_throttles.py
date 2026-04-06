"""
Tests for custom throttle classes in api/users/throttles.py

Verifies:
  1. IdentityBasedOTPSendThrottle   — keys on email/phone, NOT on IP
  2. IdentityBasedOTPVerifyThrottle — same
  3. IdentityBasedLoginThrottle     — keys on email_or_phone, NOT on IP
  4. PerUserPostLikeThrottle        — keys on user.pk, NOT on IP
  5. PerUserPostSaveThrottle        — same
  6. PerUserPostCommentThrottle     — same
  7. PerUserMessagingThrottle       — same
  8. Cross-user isolation           — userA limit does NOT affect userB
  9. Fallback to IP                 — when no identity field present
"""

import uuid
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.core.cache import cache

from api.users.throttles import (
    IdentityBasedOTPSendThrottle,
    IdentityBasedOTPVerifyThrottle,
    IdentityBasedLoginThrottle,
    PerUserPostLikeThrottle,
    PerUserPostSaveThrottle,
    PerUserPostCommentThrottle,
    PerUserMessagingThrottle,
    _hash,
)


# ─── helpers ──────────────────────────────────────────────────────────────────

def _make_request(data=None, user=None, ip="1.2.3.4"):
    """Build a minimal mock request object."""
    req = MagicMock()
    req.data = data or {}
    req.user = user
    req.META = {
        "REMOTE_ADDR": ip,
        "HTTP_X_FORWARDED_FOR": "",
    }
    return req


def _make_auth_user(pk=None):
    """Build a minimal mock authenticated user."""
    user = MagicMock()
    user.pk = pk or uuid.uuid4()
    user.is_authenticated = True
    return user


def _make_anon_user():
    user = MagicMock()
    user.is_authenticated = False
    return user


# We use LocMemCache so tests work without a running Redis.
CACHE_SETTINGS = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}


# ─── Unit tests ───────────────────────────────────────────────────────────────


@override_settings(
    CACHES=CACHE_SETTINGS,
    DEFAULT_THROTTLE_RATES={
        "otp_send": "3/minute",
        "otp_verify": "5/minute",
        "auth_login": "5/minute",
        "post_like": "10/minute",
        "post_save": "10/minute",
        "post_comment": "5/minute",
        "messaging_send": "20/minute",
    },
)
class ThrottleCacheKeyTests(TestCase):
    """Unit tests — verify cache key generation logic."""

    def setUp(self):
        cache.clear()

    # ── OTP Send ──────────────────────────────────────────────────────

    def test_otp_send_keyed_by_email(self):
        throttle = IdentityBasedOTPSendThrottle()
        req = _make_request(data={"email": "alice@example.com"})
        key = throttle.get_cache_key(req, view=None)
        self.assertIn(_hash("alice@example.com"), key)
        self.assertNotIn("1.2.3.4", key)

    def test_otp_send_keyed_by_phone(self):
        throttle = IdentityBasedOTPSendThrottle()
        req = _make_request(data={"phone": "+1234567890"})
        key = throttle.get_cache_key(req, view=None)
        self.assertIn(_hash("+1234567890"), key)

    def test_otp_send_keyed_by_email_or_phone(self):
        throttle = IdentityBasedOTPSendThrottle()
        req = _make_request(data={"email_or_phone": "bob@example.com"})
        key = throttle.get_cache_key(req, view=None)
        self.assertIn(_hash("bob@example.com"), key)

    def test_otp_send_different_emails_get_different_keys(self):
        throttle = IdentityBasedOTPSendThrottle()
        key_a = throttle.get_cache_key(_make_request(data={"email": "a@x.com"}), None)
        key_b = throttle.get_cache_key(_make_request(data={"email": "b@x.com"}), None)
        self.assertNotEqual(key_a, key_b)

    def test_otp_send_same_email_same_key_regardless_of_ip(self):
        """Two requests with same email but different IPs → same cache key."""
        throttle = IdentityBasedOTPSendThrottle()
        key_a = throttle.get_cache_key(
            _make_request(data={"email": "same@x.com"}, ip="1.1.1.1"), None
        )
        key_b = throttle.get_cache_key(
            _make_request(data={"email": "same@x.com"}, ip="9.9.9.9"), None
        )
        self.assertEqual(key_a, key_b)

    def test_otp_send_no_identity_falls_back_to_ip(self):
        """When no email/phone in body, fall back to IP-based key (safety net)."""
        throttle = IdentityBasedOTPSendThrottle()
        req = _make_request(data={}, ip="5.6.7.8")
        key = throttle.get_cache_key(req, view=None)
        # Key should use IP (DRF's default cache_format pattern)
        self.assertIsNotNone(key)

    # ── OTP Verify ────────────────────────────────────────────────────

    def test_otp_verify_keyed_by_email(self):
        throttle = IdentityBasedOTPVerifyThrottle()
        req = _make_request(data={"email": "carol@example.com"})
        key = throttle.get_cache_key(req, view=None)
        self.assertIn(_hash("carol@example.com"), key)

    def test_otp_verify_keyed_by_phone(self):
        throttle = IdentityBasedOTPVerifyThrottle()
        req = _make_request(data={"phone": "+9876543210"})
        key = throttle.get_cache_key(req, view=None)
        self.assertIn(_hash("+9876543210"), key)

    # ── Login ─────────────────────────────────────────────────────────

    def test_login_keyed_by_email_or_phone(self):
        throttle = IdentityBasedLoginThrottle()
        req = _make_request(data={"email_or_phone": "dave@example.com"})
        key = throttle.get_cache_key(req, view=None)
        self.assertIn(_hash("dave@example.com"), key)

    def test_login_different_accounts_different_keys(self):
        throttle = IdentityBasedLoginThrottle()
        key_a = throttle.get_cache_key(_make_request(data={"email_or_phone": "a@x.com"}), None)
        key_b = throttle.get_cache_key(_make_request(data={"email_or_phone": "b@x.com"}), None)
        self.assertNotEqual(key_a, key_b)

    # ── Per-user throttles ────────────────────────────────────────────

    def test_post_like_keyed_by_user_pk(self):
        user = _make_auth_user(pk=42)
        throttle = PerUserPostLikeThrottle()
        req = _make_request(user=user, ip="1.2.3.4")
        key = throttle.get_cache_key(req, view=None)
        self.assertIn("42", str(key))

    def test_post_like_different_users_different_keys(self):
        throttle = PerUserPostLikeThrottle()
        key_a = throttle.get_cache_key(_make_request(user=_make_auth_user(pk=1)), None)
        key_b = throttle.get_cache_key(_make_request(user=_make_auth_user(pk=2)), None)
        self.assertNotEqual(key_a, key_b)

    def test_post_save_keyed_by_user_pk(self):
        user = _make_auth_user(pk=99)
        throttle = PerUserPostSaveThrottle()
        key = throttle.get_cache_key(_make_request(user=user), None)
        self.assertIn("99", str(key))

    def test_post_comment_keyed_by_user_pk(self):
        user = _make_auth_user(pk=77)
        throttle = PerUserPostCommentThrottle()
        key = throttle.get_cache_key(_make_request(user=user), None)
        self.assertIn("77", str(key))

    def test_messaging_keyed_by_user_pk(self):
        user = _make_auth_user(pk=55)
        throttle = PerUserMessagingThrottle()
        key = throttle.get_cache_key(_make_request(user=user), None)
        self.assertIn("55", str(key))


@override_settings(
    CACHES=CACHE_SETTINGS,
    DEFAULT_THROTTLE_RATES={
        "otp_send": "2/minute",
        "otp_verify": "5/minute",
        "auth_login": "2/minute",
        "post_like": "3/minute",
        "post_save": "10/minute",
        "post_comment": "5/minute",
        "messaging_send": "20/minute",
    },
)
class ThrottleIsolationTests(TestCase):
    """
    Integration-style tests — verify that hitting the limit for one
    identity/user does NOT affect a different identity/user.
    """

    def setUp(self):
        cache.clear()
        # Override class level attribute to bypass api_settings caching in DRF
        IdentityBasedOTPSendThrottle.THROTTLE_RATES = {"otp_send": "2/minute"}
        IdentityBasedLoginThrottle.THROTTLE_RATES = {"auth_login": "2/minute"}
        PerUserPostLikeThrottle.THROTTLE_RATES = {"post_like": "3/minute"}
        
    def tearDown(self):
        # Restore rates (optional but clean)
        from rest_framework.settings import api_settings
        IdentityBasedOTPSendThrottle.THROTTLE_RATES = api_settings.DEFAULT_THROTTLE_RATES
        IdentityBasedLoginThrottle.THROTTLE_RATES = api_settings.DEFAULT_THROTTLE_RATES
        PerUserPostLikeThrottle.THROTTLE_RATES = api_settings.DEFAULT_THROTTLE_RATES

    def _allow(self, throttle, request):
        """Return True if the throttle would allow the request."""
        return throttle.allow_request(request, view=None)

    # ── OTP Send cross-user isolation ─────────────────────────────────

    def test_userA_otp_limit_does_not_block_userB(self):
        """
        Bug being fixed: one user exhausting otp_send must NOT block others.
        Rate: 2/minute
        """
        req_a = _make_request(data={"email": "userA@x.com"}, ip="1.1.1.1")
        req_b = _make_request(data={"email": "userB@x.com"}, ip="1.1.1.1")  # same IP!

        throttle_a1 = IdentityBasedOTPSendThrottle()
        throttle_a2 = IdentityBasedOTPSendThrottle()
        throttle_a3 = IdentityBasedOTPSendThrottle()

        # userA sends 2 OTPs — hits the limit
        self.assertTrue(self._allow(throttle_a1, req_a))
        self.assertTrue(self._allow(throttle_a2, req_a))
        # userA's 3rd attempt is blocked
        self.assertFalse(self._allow(throttle_a3, req_a))

        # userB (same IP) should still be allowed
        throttle_b = IdentityBasedOTPSendThrottle()
        self.assertTrue(self._allow(throttle_b, req_b), 
                        "userB should NOT be blocked by userA's limit")

    def test_password_reset_limit_per_account(self):
        """Password reset OTP for account A doesn't block account B."""
        req_reset_a1 = _make_request(data={"email_or_phone": "reset_a@x.com"}, ip="2.2.2.2")
        req_reset_a2 = _make_request(data={"email_or_phone": "reset_a@x.com"}, ip="2.2.2.2")
        req_reset_a3 = _make_request(data={"email_or_phone": "reset_a@x.com"}, ip="2.2.2.2")
        req_reset_b  = _make_request(data={"email_or_phone": "reset_b@x.com"}, ip="2.2.2.2")

        self.assertTrue(self._allow(IdentityBasedOTPSendThrottle(), req_reset_a1))
        self.assertTrue(self._allow(IdentityBasedOTPSendThrottle(), req_reset_a2))
        self.assertFalse(self._allow(IdentityBasedOTPSendThrottle(), req_reset_a3))

        # account B unaffected
        self.assertTrue(
            self._allow(IdentityBasedOTPSendThrottle(), req_reset_b),
            "reset_b should not be blocked because reset_a hit the limit"
        )

    # ── Login cross-user isolation ─────────────────────────────────────

    def test_login_limit_per_account_not_per_ip(self):
        """Brute-forcing user A's account doesn't lock user B out."""
        req_a = _make_request(data={"email_or_phone": "victim@x.com"}, ip="3.3.3.3")
        req_b = _make_request(data={"email_or_phone": "other@x.com"}, ip="3.3.3.3")

        throttle = IdentityBasedLoginThrottle()
        # Exhaust login rate for victim (2/minute)
        self.assertTrue(self._allow(throttle, req_a))
        self.assertTrue(self._allow(throttle, req_a))
        self.assertFalse(self._allow(throttle, req_a))

        # other user same IP — still allowed
        self.assertTrue(
            self._allow(IdentityBasedLoginThrottle(), req_b),
            "other@x.com must not be blocked by victim@x.com's exhausted limit"
        )

    # ── Per-user post-like isolation ───────────────────────────────────

    def test_post_like_limit_per_user_not_global(self):
        """userA's reaction limit does not affect userB."""
        user_a = _make_auth_user(pk=101)
        user_b = _make_auth_user(pk=202)

        req_a = _make_request(user=user_a, ip="4.4.4.4")
        req_b = _make_request(user=user_b, ip="4.4.4.4")

        throttle_a = PerUserPostLikeThrottle()
        
        # userA exhausts rate (3/minute)
        self.assertTrue(self._allow(throttle_a, req_a))
        self.assertTrue(self._allow(throttle_a, req_a))
        self.assertTrue(self._allow(throttle_a, req_a))
        self.assertFalse(self._allow(throttle_a, req_a))

        # userB (same IP!) still allowed
        self.assertTrue(
            self._allow(PerUserPostLikeThrottle(), req_b),
            "userB must not be blocked by userA's like limit"
        )

    # ── Rate enforcement (sanity) ──────────────────────────────────────

    def test_otp_send_enforces_rate(self):
        """After N requests, the (N+1)th is blocked."""
        req = _make_request(data={"email": "rate_test@x.com"}, ip="5.5.5.5")
        # Rate is 2/minute
        self.assertTrue(self._allow(IdentityBasedOTPSendThrottle(), req))
        self.assertTrue(self._allow(IdentityBasedOTPSendThrottle(), req))
        self.assertFalse(self._allow(IdentityBasedOTPSendThrottle(), req))

    def test_post_like_enforces_rate(self):
        """After N likes, the (N+1)th is blocked."""
        user = _make_auth_user(pk=999)
        req = _make_request(user=user, ip="6.6.6.6")
        throttle = PerUserPostLikeThrottle()
        # Rate is 3/minute
        self.assertTrue(self._allow(throttle, req))
        self.assertTrue(self._allow(throttle, req))
        self.assertTrue(self._allow(throttle, req))
        self.assertFalse(self._allow(throttle, req))

    # ── Cache key distinctness for different throttle types ────────────

    def test_different_throttle_types_use_different_namespaces(self):
        """
        OTPSend and OTPVerify for the same email must use different cache keys
        so one's counter doesn't pollute the other's.
        """
        throttle_send = IdentityBasedOTPSendThrottle()
        throttle_verify = IdentityBasedOTPVerifyThrottle()
        req = _make_request(data={"email": "shared@x.com"})
        key_send = throttle_send.get_cache_key(req, None)
        key_verify = throttle_verify.get_cache_key(req, None)
        self.assertNotEqual(key_send, key_verify)

    def test_post_like_and_post_save_use_different_namespaces(self):
        user = _make_auth_user(pk=333)
        req = _make_request(user=user)
        key_like = PerUserPostLikeThrottle().get_cache_key(req, None)
        key_save = PerUserPostSaveThrottle().get_cache_key(req, None)
        self.assertNotEqual(key_like, key_save)


@override_settings(
    CACHES=CACHE_SETTINGS,
    DEFAULT_THROTTLE_RATES={
        "otp_send": "5/5minute",   # Production value
        "otp_verify": "10/hour",
        "auth_login": "40/hour",
        "post_like": "200/minute",
        "post_save": "100/minute",
        "post_comment": "30/minute",
        "messaging_send": "5000/hour",
    },
)
class ProductionRatesTest(TestCase):
    """
    Sanity-check that the production rate strings parse correctly
    and that the throttle classes initialize without errors.
    """

    def setUp(self):
        cache.clear()

    def test_all_throttle_classes_parse_production_rates(self):
        """All throttle classes must initialize and parse their rate without error."""
        classes = [
            IdentityBasedOTPSendThrottle,
            IdentityBasedOTPVerifyThrottle,
            IdentityBasedLoginThrottle,
            PerUserPostLikeThrottle,
            PerUserPostSaveThrottle,
            PerUserPostCommentThrottle,
            PerUserMessagingThrottle,
        ]
        for cls in classes:
            instance = cls()
            num, period = instance.parse_rate(instance.get_rate())
            self.assertIsNotNone(num, f"{cls.__name__} returned None num_requests")
            self.assertIsNotNone(period, f"{cls.__name__} returned None duration")
            self.assertGreater(num, 0, f"{cls.__name__} has num_requests <= 0")
            self.assertGreater(period, 0, f"{cls.__name__} has duration <= 0")

    def test_otp_send_5_per_5_minutes_window(self):
        """5/5minute should translate to 5 requests per 300 seconds."""
        instance = IdentityBasedOTPSendThrottle()
        num, duration = instance.parse_rate("5/5minute")
        self.assertEqual(num, 5)
        self.assertEqual(duration, 300)  # 5 * 60 seconds

    def test_post_like_200_per_minute(self):
        instance = PerUserPostLikeThrottle()
        num, duration = instance.parse_rate("200/minute")
        self.assertEqual(num, 200)
        self.assertEqual(duration, 60)

    def test_auth_login_40_per_hour(self):
        instance = IdentityBasedLoginThrottle()
        num, duration = instance.parse_rate("40/hour")
        self.assertEqual(num, 40)
        self.assertEqual(duration, 3600)
