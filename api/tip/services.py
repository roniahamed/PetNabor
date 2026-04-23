"""
Tip System Services — all Stripe API interactions live here.

Views call these functions; they never call stripe directly.
"""

import logging
import stripe
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import transaction

from .models import (
    TipSettings,
    StripeConnectAccount,
    Tip,
    TipStatus,
    TipWithdrawal,
    WithdrawalStatus,
)
from api.notifications.services import send_notification
from api.notifications.models import NotificationTypes

logger = logging.getLogger(__name__)


# Configure stripe key lazily to respect settings load order
def _stripe():
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


# ──────────────────────────────────────────────────────────────────────────────
# Stripe Connect — Onboarding
# ──────────────────────────────────────────────────────────────────────────────


def create_connect_account(user):
    """
    Create a Stripe Express Connected Account for a user and generate
    an onboarding URL. Returns (connect_account, onboarding_url).

    If the user already has a connect account, returns the existing one
    plus a fresh account link URL.
    """
    s = _stripe()

    # Reuse existing account if present
    try:
        connect = user.stripe_connect_account
        onboarding_url = _get_account_link(connect.stripe_account_id)
        return connect, onboarding_url
    except StripeConnectAccount.DoesNotExist:
        pass

    # Build metadata for the Express account
    email = user.email or ""
    frontend_url = getattr(settings, "FRONTEND_BASE_URL", "petnabor://")
    # Stripe requires a valid HTTPS URL for business_profile.url
    business_url = getattr(settings, "BUSINESS_URL", "https://petnabor.com")

    account = s.Account.create(
        type="express",
        email=email,
        business_type="individual",
        business_profile={
            # MCC 7299 = "Other personal services" — fits peer tipping on a pet social app
            "mcc": "7299",
            "url": business_url,
        },
        capabilities={
            "card_payments": {"requested": True},
            "transfers": {"requested": True},
        },
        metadata={"user_id": str(user.id)},
    )

    connect = StripeConnectAccount.objects.create(
        user=user,
        stripe_account_id=account.id,
    )

    onboarding_url = _get_account_link(account.id)
    return connect, onboarding_url


def _get_account_link(account_id, return_url=None, refresh_url=None):
    """
    Generate a short-lived Stripe Account Link URL for onboarding.

    Stripe requires HTTPS URLs. We use the backend as a bridge which then
    redirects to the mobile app's deep link (petnabor://).
    """
    s = _stripe()
    domain = getattr(settings, "BACKEND_BASE_URL", "https://backend.petnabor.com")
    link = s.AccountLink.create(
        account=account_id,
        refresh_url=refresh_url or f"{domain}/api/tip/onboard/bridge/?status=refresh",
        return_url=return_url or f"{domain}/api/tip/onboard/bridge/?status=return",
        type="account_onboarding",
    )
    return link.url


def refresh_onboarding_link(user):
    """
    Return a fresh onboarding URL for an existing (but incomplete) account.
    Raises StripeConnectAccount.DoesNotExist if no account yet.
    """
    connect = user.stripe_connect_account
    return _get_account_link(connect.stripe_account_id)


def get_connect_account_status(user):
    """
    Fetch live status from Stripe and sync it to the DB.
    Returns the updated StripeConnectAccount instance.
    """
    s = _stripe()
    try:
        connect = user.stripe_connect_account
    except StripeConnectAccount.DoesNotExist:
        return None

    account = s.Account.retrieve(connect.stripe_account_id)
    connect.is_charges_enabled = account.charges_enabled
    connect.is_payouts_enabled = account.payouts_enabled
    connect.is_onboarding_complete = (
        account.details_submitted and account.charges_enabled
    )
    connect.save(
        update_fields=[
            "is_charges_enabled",
            "is_payouts_enabled",
            "is_onboarding_complete",
            "updated_at",
        ]
    )
    return connect


# ──────────────────────────────────────────────────────────────────────────────
# Tip — Payment Intent
# ──────────────────────────────────────────────────────────────────────────────


def calculate_commission(amount: Decimal, commission_percentage: Decimal):
    """
    Returns (commission_amount, recipient_amount) both as Decimal.
    Rounds half-up to 2 decimal places.
    """
    commission = (amount * commission_percentage / Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    recipient = amount - commission
    return commission, recipient


def create_tip_payment_intent(
    tipper, recipient, amount: Decimal, meeting=None, note=""
):
    """
    Create a Stripe PaymentIntent for a tip.

    TWO FLOWS:
    1. Recipient HAS verified Connect account:
       → PaymentIntent with transfer_data + application_fee_amount
       → Money goes directly to recipient's account after payment
       → Tip status = PENDING

    2. Recipient does NOT have a verified Connect account:
       → PaymentIntent WITHOUT transfer_data (money held on platform)
       → Tip status = HELD
       → Recipient gets a push notification to connect their account
       → When they connect, release_held_tips() transfers the money automatically
    """
    s = _stripe()
    tip_settings = TipSettings.get_instance()

    commission_pct = tip_settings.commission_percentage
    commission_amount, recipient_amount = calculate_commission(amount, commission_pct)

    amount_cents = int(amount * 100)
    commission_cents = int(commission_amount * 100)

    # Check if recipient has a verified connect account
    connect = None
    has_verified_account = False
    try:
        connect = recipient.stripe_connect_account
        has_verified_account = connect.is_fully_verified
    except StripeConnectAccount.DoesNotExist:
        pass

    if has_verified_account:
        # ── Direct transfer flow ──────────────────────────────────────────────
        intent = s.PaymentIntent.create(
            amount=amount_cents,
            currency="usd",
            application_fee_amount=commission_cents,
            transfer_data={"destination": connect.stripe_account_id},
            metadata={
                "tipper_id": str(tipper.id),
                "recipient_id": str(recipient.id),
                "meeting_id": str(meeting.id) if meeting else "",
                "flow": "direct",
            },
            automatic_payment_methods={"enabled": True},
        )
        tip_status = TipStatus.PENDING

    else:
        # ── Hold flow: charge platform, transfer later ────────────────────────
        intent = s.PaymentIntent.create(
            amount=amount_cents,
            currency="usd",
            # No transfer_data — money stays on platform until recipient connects
            metadata={
                "tipper_id": str(tipper.id),
                "recipient_id": str(recipient.id),
                "meeting_id": str(meeting.id) if meeting else "",
                "flow": "held",
            },
            automatic_payment_methods={"enabled": True},
        )
        tip_status = TipStatus.HELD

        # Notify recipient to connect their Stripe account
        try:
            send_notification(
                title="Someone sent you a tip!",
                body=(
                    f"{tipper.first_name or 'Someone'} sent you a "
                    f"${amount:.2f} tip! Connect your bank account to receive it."
                ),
                user_id=recipient.id,
                notification_type=NotificationTypes.TIP_ENABLE_REQUEST,
                data={"action": "connect_stripe", "amount": str(amount)},
            )
        except Exception as exc:
            logger.warning("Failed to notify recipient about held tip: %s", exc)

    tip = Tip.objects.create(
        tipper=tipper,
        recipient=recipient,
        meeting=meeting,
        amount=amount,
        commission_percentage=commission_pct,
        commission_amount=commission_amount,
        recipient_amount=recipient_amount,
        stripe_payment_intent_id=intent.id,
        status=tip_status,
        note=note,
        currency="usd",
    )

    return tip, intent.client_secret


# ──────────────────────────────────────────────────────────────────────────────
# Hold & Release
# ──────────────────────────────────────────────────────────────────────────────


def transfer_held_tip(tip, connect):
    """
    Transfer a single held tip to the recipient's Connect account.

    When a recipient connects their Stripe account, we create a Stripe Transfer
    using the original charge as source_transaction. The platform keeps the
    commission (difference between charge amount and transfer amount).
    """
    s = _stripe()

    if not tip.stripe_charge_id:
        logger.warning(
            "Cannot release held tip %s — no charge_id yet (payment not confirmed)", tip.id
        )
        return False

    recipient_cents = int(tip.recipient_amount * 100)

    try:
        transfer = s.Transfer.create(
            amount=recipient_cents,
            currency="usd",
            destination=connect.stripe_account_id,
            source_transaction=tip.stripe_charge_id,
            metadata={"tip_id": str(tip.id), "tipper_id": str(tip.tipper_id)},
        )
    except Exception as exc:
        logger.error("Stripe transfer failed for held tip %s: %s", tip.id, str(exc))
        return False

    with transaction.atomic():
        tip.status = TipStatus.SUCCEEDED
        tip.stripe_transfer_id = transfer.id
        tip.save(update_fields=["status", "stripe_transfer_id", "updated_at"])

    logger.info(
        "Released held tip %s → Transfer %s to %s",
        tip.id, transfer.id, connect.stripe_account_id,
    )

    # Notify both parties
    try:
        send_notification(
            title="Tip received!",
            body=f"${tip.amount:.2f} tip has been added to your account.",
            user_id=tip.recipient_id,
            notification_type=NotificationTypes.TIP_RECEIVED,
            data={"tip_id": str(tip.id)},
        )
        send_notification(
            title="Your tip was delivered!",
            body=(
                f"Your ${tip.amount:.2f} tip has been sent to "
                f"{tip.recipient.first_name or 'the recipient'}."
            ),
            user_id=tip.tipper_id,
            notification_type=NotificationTypes.TIP_SENT,
            data={"tip_id": str(tip.id)},
        )
    except Exception as exc:
        logger.warning("Notification failed after tip release: %s", exc)

    return True


def release_held_tips(user):
    """
    Release all held tips for a user who has just connected their Stripe account.
    Called from handle_account_updated when the account becomes fully verified.

    Only releases tips where payment has already been confirmed (charge_id exists).
    Tips that are still PENDING payment will be handled by handle_payment_intent_succeeded.
    """
    try:
        connect = user.stripe_connect_account
    except StripeConnectAccount.DoesNotExist:
        return

    if not connect.is_fully_verified:
        return

    held_tips = Tip.objects.filter(
        recipient=user,
        status=TipStatus.HELD,
        stripe_charge_id__isnull=False,  # Payment confirmed, waiting for account
    ).select_related("tipper", "recipient")

    if not held_tips.exists():
        logger.info("No held tips to release for user %s", user.id)
        return

    logger.info(
        "Releasing %d held tip(s) for user %s (account: %s)",
        held_tips.count(), user.id, connect.stripe_account_id,
    )

    for tip in held_tips:
        try:
            transfer_held_tip(tip, connect)
        except Exception as exc:
            logger.error(
                "Failed to release held tip %s for user %s: %s",
                tip.id, user.id, str(exc),
            )


# ──────────────────────────────────────────────────────────────────────────────
# Webhook Handlers
# ──────────────────────────────────────────────────────────────────────────────


def handle_payment_intent_succeeded(payment_intent):
    """Mark the tip as succeeded and capture the charge ID.

    Special case for HELD tips:
    - If tip is HELD, only update the charge_id (money is on platform).
    - The actual transfer happens in release_held_tips() when user connects.
    - If tip is PENDING (direct flow), mark it SUCCEEDED normally.
    """
    pi_id = payment_intent["id"]
    charge_id = payment_intent.get("latest_charge") or payment_intent.get(
        "charges", {}
    ).get("data", [{}])[0].get("id")

    with transaction.atomic():
        try:
            tip = Tip.objects.select_for_update().get(stripe_payment_intent_id=pi_id)
        except Tip.DoesNotExist:
            logger.warning("Webhook: Tip not found for payment_intent %s", pi_id)
            return

        if tip.status == TipStatus.SUCCEEDED:
            return  # Idempotent

        if tip.status == TipStatus.HELD:
            # Payment confirmed but recipient has no account yet.
            # Store charge_id so we can transfer later when they connect.
            tip.stripe_charge_id = charge_id
            tip.save(update_fields=["stripe_charge_id", "updated_at"])
            logger.info(
                "Held tip %s payment confirmed (charge: %s) — awaiting recipient account",
                tip.id, charge_id,
            )

            # Re-notify recipient that a real payment is waiting
            try:
                send_notification(
                    title="Payment confirmed — waiting for you!",
                    body=(
                        f"A ${tip.amount:.2f} tip is ready for you. "
                        "Connect your bank account to receive it immediately."
                    ),
                    user_id=tip.recipient_id,
                    notification_type=NotificationTypes.TIP_ENABLE_REQUEST,
                    data={"action": "connect_stripe", "tip_id": str(tip.id)},
                )
            except Exception as exc:
                logger.warning("Notification failed for held tip: %s", exc)
            return

        # Normal PENDING → SUCCEEDED
        tip.status = TipStatus.SUCCEEDED
        tip.stripe_charge_id = charge_id
        tip.save(update_fields=["status", "stripe_charge_id", "updated_at"])
        logger.info("Tip %s succeeded (PI: %s)", tip.id, pi_id)


def handle_payment_intent_failed(payment_intent):
    """Mark the tip as failed."""
    pi_id = payment_intent["id"]

    with transaction.atomic():
        try:
            tip = Tip.objects.select_for_update().get(stripe_payment_intent_id=pi_id)
        except Tip.DoesNotExist:
            logger.warning("Webhook: Tip not found for failed payment_intent %s", pi_id)
            return

        if tip.status in (TipStatus.SUCCEEDED, TipStatus.FAILED):
            return

        tip.status = TipStatus.FAILED
        tip.save(update_fields=["status", "updated_at"])
        logger.info("Tip %s failed (PI: %s)", tip.id, pi_id)


def handle_payment_intent_cancelled(payment_intent):
    """Mark the tip as cancelled."""
    pi_id = payment_intent["id"]

    with transaction.atomic():
        try:
            tip = Tip.objects.select_for_update().get(stripe_payment_intent_id=pi_id)
        except Tip.DoesNotExist:
            return

        tip.status = TipStatus.CANCELLED
        tip.save(update_fields=["status", "updated_at"])


def handle_charge_refunded(charge):
    """Mark the tip as refunded when the charge is refunded."""
    charge_id = charge["id"]

    with transaction.atomic():
        try:
            tip = Tip.objects.select_for_update().get(stripe_charge_id=charge_id)
        except Tip.DoesNotExist:
            logger.warning("Webhook: Tip not found for refunded charge %s", charge_id)
            return

        tip.status = TipStatus.REFUNDED
        tip.save(update_fields=["status", "updated_at"])
        logger.info("Tip %s refunded (charge: %s)", tip.id, charge_id)


def handle_account_updated(account):
    """Sync Stripe Connect account status when account.updated fires.

    When an account becomes fully verified for the first time,
    automatically release any HELD tips waiting for this user.
    """
    account_id = account["id"]

    try:
        connect = StripeConnectAccount.objects.get(stripe_account_id=account_id)
    except StripeConnectAccount.DoesNotExist:
        logger.warning("Webhook: StripeConnectAccount not found for %s", account_id)
        return

    was_verified = connect.is_fully_verified

    connect.is_charges_enabled = account.get("charges_enabled", False)
    connect.is_payouts_enabled = account.get("payouts_enabled", False)
    connect.is_onboarding_complete = (
        account.get("details_submitted", False) and connect.is_charges_enabled
    )
    connect.save(
        update_fields=[
            "is_charges_enabled",
            "is_payouts_enabled",
            "is_onboarding_complete",
            "updated_at",
        ]
    )
    logger.info(
        "Connect account %s synced: charges=%s payouts=%s",
        account_id,
        connect.is_charges_enabled,
        connect.is_payouts_enabled,
    )

    # If account JUST became fully verified, release any held tips
    if not was_verified and connect.is_fully_verified:
        logger.info(
            "Account %s just verified — releasing held tips for user %s",
            account_id, connect.user_id,
        )
        try:
            release_held_tips(connect.user)
        except Exception as exc:
            logger.error(
                "Error releasing held tips for user %s: %s", connect.user_id, str(exc)
            )


def handle_payout_paid(payout):
    """Mark a withdrawal as paid when the payout succeeds."""
    payout_id = payout["id"]

    with transaction.atomic():
        try:
            withdrawal = TipWithdrawal.objects.select_for_update().get(
                stripe_payout_id=payout_id
            )
        except TipWithdrawal.DoesNotExist:
            logger.warning("Webhook: TipWithdrawal not found for payout %s", payout_id)
            return

        withdrawal.status = WithdrawalStatus.PAID
        withdrawal.save(update_fields=["status", "updated_at"])
        logger.info("Withdrawal %s paid (payout: %s)", withdrawal.id, payout_id)


def handle_payout_failed(payout):
    """Mark a withdrawal as failed when the payout fails."""
    payout_id = payout["id"]

    with transaction.atomic():
        try:
            withdrawal = TipWithdrawal.objects.select_for_update().get(
                stripe_payout_id=payout_id
            )
        except TipWithdrawal.DoesNotExist:
            logger.warning(
                "Webhook: TipWithdrawal not found for failed payout %s", payout_id
            )
            return

        failure_msg = payout.get("failure_message") or payout.get(
            "failure_code", "Unknown failure"
        )
        withdrawal.status = WithdrawalStatus.FAILED
        withdrawal.failure_message = failure_msg
        withdrawal.save(update_fields=["status", "failure_message", "updated_at"])
        logger.info(
            "Withdrawal %s failed (payout: %s): %s",
            withdrawal.id,
            payout_id,
            failure_msg,
        )


# ──────────────────────────────────────────────────────────────────────────────
# Withdrawal (Payout)
# ──────────────────────────────────────────────────────────────────────────────


def get_stripe_balance(user):
    """
    Retrieve the available balance from the user's Stripe Connected Account.
    Returns the available USD balance in dollars (Decimal).
    """
    s = _stripe()
    try:
        connect = user.stripe_connect_account
    except StripeConnectAccount.DoesNotExist:
        return Decimal("0.00")

    if not connect.is_fully_verified:
        return Decimal("0.00")

    balance = s.Balance.retrieve(stripe_account=connect.stripe_account_id)
    available = balance.get("available", [])
    for entry in available:
        if entry["currency"] == "usd":
            return Decimal(str(entry["amount"])) / Decimal("100")
    return Decimal("0.00")


def create_withdrawal(user, amount: Decimal):
    """
    Create a Stripe Payout on the user's Connected Account.
    Returns the TipWithdrawal instance.

    Raises ValueError for validation failures (not verified, amount too low, etc.)
    """
    s = _stripe()
    tip_settings = TipSettings.get_instance()

    # Validate connect account
    try:
        connect = user.stripe_connect_account
    except StripeConnectAccount.DoesNotExist:
        raise ValueError("You must connect your Stripe account before withdrawing.")

    if not connect.is_fully_verified:
        raise ValueError(
            "Your Stripe account is not fully verified. Please complete onboarding."
        )

    # Validate minimum amount
    if amount < tip_settings.minimum_withdrawal_amount:
        raise ValueError(
            f"Minimum withdrawal amount is ${tip_settings.minimum_withdrawal_amount}."
        )

    # Check available balance
    available = get_stripe_balance(user)
    if amount > available:
        raise ValueError(
            f"Insufficient balance. Available: ${available:.2f}, Requested: ${amount:.2f}."
        )

    amount_cents = int(amount * 100)

    payout = s.Payout.create(
        amount=amount_cents,
        currency="usd",
        stripe_account=connect.stripe_account_id,
        metadata={"user_id": str(user.id)},
    )

    withdrawal = TipWithdrawal.objects.create(
        user=user,
        connect_account=connect,
        amount=amount,
        currency="usd",
        stripe_payout_id=payout.id,
        status=WithdrawalStatus.PENDING,
    )

    return withdrawal


def construct_stripe_event(payload, sig_header):
    """
    Verify the Stripe webhook signature and construct the event object.
    Raises stripe.error.SignatureVerificationError on failure.
    """
    s = _stripe()
    return s.Webhook.construct_event(
        payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
    )
