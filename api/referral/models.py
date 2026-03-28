"""
Referral System Models.

- ReferralSettings: singleton for admin-configurable point values
- ReferralWallet: per-user balance
- ReferralTransaction: immutable ledger of every credit / debit
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models


# ──────────────────────────────────────────────
# Settings (Singleton)
# ──────────────────────────────────────────────


class ReferralSettings(models.Model):
    """
    Admin-editable global settings for the referral programme.

    There should only ever be ONE row in this table.
    The admin is configured to enforce that.
    """

    referrer_points = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("10.00"),
        help_text="Points awarded to the user who referred a friend.",
    )
    referee_points = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("5.00"),
        help_text="Points awarded to the new user who signed up via a referral.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Referral Settings"
        verbose_name_plural = "Referral Settings"

    def __str__(self):
        return f"Referral Settings (referrer={self.referrer_points}, referee={self.referee_points})"

    @classmethod
    def get_instance(cls):
        """Return the singleton settings row, creating it with defaults if absent."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# ──────────────────────────────────────────────
# Wallet
# ──────────────────────────────────────────────


class ReferralWallet(models.Model):
    """Per-user wallet that accumulates referral points."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referral_wallet",
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Wallet({self.user}) balance={self.balance}"


# ──────────────────────────────────────────────
# Transaction Ledger
# ──────────────────────────────────────────────


class TransactionType(models.TextChoices):
    SIGNUP_BONUS = "signup_bonus", "Signup Bonus"
    REFERRAL_COMMISSION = "referral_commission", "Referral Commission"
    WITHDRAWAL = "withdrawal", "Withdrawal"


class TransactionStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class ReferralTransaction(models.Model):
    """Immutable ledger entry for every credit or debit."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        ReferralWallet,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    # Optional: who triggered this transaction (the other party)
    related_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_referral_transactions",
    )
    transaction_type = models.CharField(
        max_length=30,
        choices=TransactionType.choices,
        default=TransactionType.REFERRAL_COMMISSION,
    )
    status = models.CharField(
        max_length=20,
        choices=TransactionStatus.choices,
        default=TransactionStatus.COMPLETED,
    )
    # Positive = credit, negative = debit
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    note = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        direction = "+" if self.amount >= 0 else ""
        return f"{self.transaction_type} {direction}{self.amount} [{self.status}]"
