"""
Asynchronous tasks for the users app.
"""
import logging
from celery import shared_task
from django.conf import settings
from api.notifications.email_service import EmailService

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
