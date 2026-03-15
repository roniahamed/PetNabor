from unittest.mock import patch
from django.test import TestCase, override_settings
from api.users.tasks import send_otp_email_task, send_otp_sms_task
from api.notifications.email_service import EmailService

class TaskTests(TestCase):
    """
    Verification of Celery tasks and EmailService.
    """

    @patch("api.notifications.email_service.EmailService.send_otp_email")
    def test_send_otp_email_task_success(self, mock_send):
        mock_send.return_value = True
        send_otp_email_task("test@example.com", "1234", 5)
        mock_send.assert_called_once_with("test@example.com", "1234", 5)

    @patch("api.notifications.email_service.EmailService.send_password_reset_email")
    def test_send_otp_email_task_password_reset(self, mock_send):
        mock_send.return_value = True
        send_otp_email_task("test@example.com", "1234", 5, is_password_reset=True)
        mock_send.assert_called_once_with("test@example.com", "1234", 5)

    @patch("twilio.rest.Client")
    @override_settings(TWILIO_ACCOUNT_SID="sid", TWILIO_AUTH_TOKEN="token", TWILIO_PHONE_NUMBER="+1234")
    def test_send_otp_sms_task_success(self, mock_client):
        mock_instance = mock_client.return_value
        send_otp_sms_task("+9876543210", "1234", 5)
        mock_instance.messages.create.assert_called_once()
        
    @patch("api.notifications.email_service.send_mail")
    @override_settings(DEFAULT_FROM_EMAIL="noreply@test.com")
    def test_email_service_send_html(self, mock_send_mail):
        EmailService.send_html_email("Subject", "<p>Hello</p>", ["to@example.com"])
        mock_send_mail.assert_called_once_with(
            subject="Subject",
            message="Hello",
            from_email="noreply@test.com",
            recipient_list=["to@example.com"],
            html_message="<p>Hello</p>",
            fail_silently=False,
        )
