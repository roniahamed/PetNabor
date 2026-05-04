"""
Management command: release_held_tips

Manually scan for held tips whose recipient now has a charges-enabled
Stripe Connect account and release the funds.

Usage:
    python manage.py release_held_tips              # dry run
    python manage.py release_held_tips --commit     # actually transfer
    python manage.py release_held_tips --user <email|phone|uuid> --commit
"""
import logging
import uuid as uuid_mod

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from api.tip.models import Tip, TipStatus
from api.tip.services import transfer_held_tip

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = "Release HELD tips for recipients who now have a verified Stripe account."

    def add_arguments(self, parser):
        parser.add_argument(
            "--commit",
            action="store_true",
            default=False,
            help="Actually execute the Stripe transfers. Without this flag the command is a dry run.",
        )
        parser.add_argument(
            "--user",
            type=str,
            default=None,
            help="Target a specific recipient by email, phone number, or UUID. If omitted, all eligible users are processed.",
        )

    def handle(self, *args, **options):
        commit = options["commit"]
        user_filter = options["user"]

        mode = "LIVE" if commit else "DRY RUN"
        self.stdout.write(self.style.WARNING(f"[{mode}] Scanning for held tips..."))

        qs = Tip.objects.filter(
            status=TipStatus.HELD,
            stripe_charge_id__isnull=False,
        ).select_related("tipper", "recipient", "recipient__stripe_connect_account")

        if user_filter:
            target_user = None

            # Try email
            try:
                target_user = User.objects.get(email=user_filter)
            except (User.DoesNotExist, Exception):
                pass

            # Try phone number
            if target_user is None:
                try:
                    target_user = User.objects.get(phone=user_filter)
                except (User.DoesNotExist, Exception):
                    pass

            # Try UUID
            if target_user is None:
                try:
                    uid = uuid_mod.UUID(str(user_filter))
                    target_user = User.objects.get(id=uid)
                except (ValueError, User.DoesNotExist):
                    pass

            if target_user is None:
                self.stderr.write(self.style.ERROR(
                    f"User not found: {user_filter} (tried email, phone, and UUID)"
                ))
                return

            qs = qs.filter(recipient=target_user)
            self.stdout.write(f"Targeting user: {target_user.email or target_user.id}")

        total = qs.count()
        self.stdout.write(f"Found {total} held tip(s) with confirmed charges.")

        released = 0
        skipped = 0
        errors = 0

        for tip in qs:
            recipient = tip.recipient
            if recipient is None:
                self.stdout.write(
                    self.style.WARNING(f"  Tip {tip.id}: recipient deleted - skipping")
                )
                skipped += 1
                continue

            connect = getattr(recipient, "stripe_connect_account", None)
            if connect is None:
                self.stdout.write(
                    f"  Tip {tip.id} (${tip.amount}): {recipient.email} has no Stripe account - skipping"
                )
                skipped += 1
                continue

            if not (connect.is_charges_enabled and connect.is_onboarding_complete):
                self.stdout.write(
                    f"  Tip {tip.id} (${tip.amount}): {recipient.email} account not ready "
                    f"(charges={connect.is_charges_enabled} onboarding={connect.is_onboarding_complete}) - skipping"
                )
                skipped += 1
                continue

            self.stdout.write(
                f"  Tip {tip.id} (${tip.amount}): {tip.tipper.email if tip.tipper else '?'} -> "
                f"{recipient.email} | Stripe: {connect.stripe_account_id}"
            )

            if commit:
                try:
                    success = transfer_held_tip(tip, connect)
                    if success:
                        self.stdout.write(self.style.SUCCESS("    Released"))
                        released += 1
                    else:
                        self.stdout.write(self.style.ERROR("    Transfer returned False (check logs)"))
                        errors += 1
                except Exception as exc:
                    self.stdout.write(self.style.ERROR(f"    Error: {exc}"))
                    errors += 1
            else:
                self.stdout.write("    Would release (use --commit to execute)")
                released += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"[{mode}] Done - Released: {released}, Skipped: {skipped}, Errors: {errors}"
        ))
        if not commit:
            self.stdout.write(
                self.style.WARNING("Dry run complete. Re-run with --commit to execute transfers.")
            )
