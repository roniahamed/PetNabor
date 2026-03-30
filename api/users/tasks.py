"""
Asynchronous tasks for the users app.
"""
import logging

from celery import shared_task
from django.conf import settings

from api.media_utils import compress_image_to_webp
from api.notifications.email_service import EmailService
from .models import Profile

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_otp_email_task(self, email, otp_code, expiry_minutes, is_password_reset=False):
    """
    Celery task to send OTP emails asynchronously.
    """
    try:
        if is_password_reset:
            success = EmailService.send_password_reset_email(email, otp_code, expiry_minutes)
        else:
            success = EmailService.send_otp_email(email, otp_code, expiry_minutes)
            
        if not success:
            raise Exception("Email delivery failed")
    except Exception as exc:
        logger.error(f"Error sending OTP email to {email}: {exc}")
        raise self.retry(exc=exc)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_otp_sms_task(self, phone, otp_code, expiry_minutes):
    """
    Celery task to send OTP SMS asynchronously via Twilio.
    """
    try:
        from twilio.rest import Client

        account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", "")
        auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", "")
        from_number = getattr(settings, "TWILIO_PHONE_NUMBER", "")

        if not all([account_sid, auth_token, from_number]):
            logger.error("Twilio credentials are not configured.")
            return

        client = Client(account_sid, auth_token)
        client.messages.create(
            body=f"Your PatNabor verification code is: {otp_code}. It expires in {expiry_minutes} minutes.",
            from_=from_number,
            to=phone,
        )
        logger.info(f"SMS OTP sent to {phone}")
    except Exception as exc:
        logger.error(f"Error sending SMS to {phone}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def process_profile_media_task(self, profile_id: str, field_name: str):
    """Compress Profile image fields asynchronously and replace old file links."""
    if field_name not in {"profile_picture", "cover_photo"}:
        logger.warning("Invalid profile media field: %s", field_name)
        return

    try:
        profile = Profile.objects.get(id=profile_id)
    except Profile.DoesNotExist:
        logger.error("Profile %s not found for media processing.", profile_id)
        return

    media_field = getattr(profile, field_name, None)
    if not media_field:
        return

    old_name = media_field.name
    compressed = compress_image_to_webp(media_field)
    if not compressed:
        return

    try:
        media_field.save(compressed.name, compressed, save=False)
        profile.save(update_fields=[field_name])

        new_name = getattr(profile, field_name).name
        if old_name and old_name != new_name:
            getattr(profile, field_name).storage.delete(old_name)
    except Exception as exc:
        logger.exception(
            "Failed to process profile media for profile=%s field=%s: %s",
            profile_id,
            field_name,
            exc,
        )
        raise self.retry(exc=exc)
