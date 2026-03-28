"""
Referral service layer.

- award_referral_points: credit both the referrer and the new user
"""
from decimal import Decimal

from django.db import transaction as db_transaction

from .models import ReferralSettings, ReferralTransaction, ReferralWallet, TransactionType, TransactionStatus


def get_or_create_wallet(user):
    """Return (or lazily create) the wallet for a user."""
    wallet, _ = ReferralWallet.objects.get_or_create(user=user)
    return wallet


def _credit(wallet, amount: Decimal, tx_type: str, related_user=None, note: str = ""):
    """Add points to a wallet and record the transaction."""
    wallet.balance += amount
    wallet.save(update_fields=["balance", "updated_at"])
    ReferralTransaction.objects.create(
        wallet=wallet,
        related_user=related_user,
        transaction_type=tx_type,
        status=TransactionStatus.COMPLETED,
        amount=amount,
        note=note,
    )


@db_transaction.atomic
def award_referral_points(new_user):
    """
    Called once when a new user who was referred completes registration.

    - Referrer receives `referrer_points` (referral_commission).
    - New user receives `referee_points` (signup_bonus).
    """
    try:
        profile = new_user.profile
    except Exception:
        return

    referrer = profile.referred_by
    if not referrer:
        return

    cfg = ReferralSettings.get_instance()

    # Credit the referrer
    referrer_wallet = get_or_create_wallet(referrer)
    _credit(
        referrer_wallet,
        cfg.referrer_points,
        TransactionType.REFERRAL_COMMISSION,
        related_user=new_user,
        note=f"Commission for referring {new_user.email or new_user.phone}",
    )

    # Credit the new user (signup bonus)
    new_wallet = get_or_create_wallet(new_user)
    _credit(
        new_wallet,
        cfg.referee_points,
        TransactionType.SIGNUP_BONUS,
        related_user=referrer,
        note=f"Signup bonus from referral code of {referrer.email or referrer.phone}",
    )
