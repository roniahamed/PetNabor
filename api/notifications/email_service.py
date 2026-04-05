"""
Branded email delivery service for the notifications app.
"""
import logging
from django.core.mail import send_mail
from django.conf import settings
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

class EmailService:
    """
    Reusable service for sending HTML/Plain emails via Gmail SMTP.
    Consolidates branding and email delivery logic.
    """
    
    @staticmethod
    def send_html_email(subject, html_content, recipient_list, from_email=None):
        """
        Sends an HTML email with a plain-text fallback.
        """
        if not from_email:
            from_email = settings.DEFAULT_FROM_EMAIL
            
        plain_message = strip_tags(html_content)
        
        try:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=from_email,
                recipient_list=recipient_list,
                html_message=html_content,
                fail_silently=False,
            )
            logger.info(f"Email sent successfully: {subject} to {recipient_list}")
            return True
        except Exception as e:
            logger.exception(f"Failed to send email: {subject} to {recipient_list}. Error: {e}")
            return False

    @classmethod
    def send_otp_email(cls, email, otp_code, expiry_minutes, subject="Your PatNabor Verification Code"):
        """
        Specialized method for sending OTP emails with PatNabor branding.
        """
        html_message = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px; text-align: center;">
                <h1 style="color: white; margin: 0;">PatNabor</h1>
            </div>
            <div style="padding: 30px; background: #f9f9f9; border-radius: 0 0 10px 10px;">
                <h2 style="color: #333;">Security Verification</h2>
                <p style="color: #666; font-size: 16px;">
                    Use the following code to complete your verification:
                </p>
                <div style="text-align: center; margin: 30px 0;">
                    <div style="background: #fff; border: 2px dashed #667eea; border-radius: 10px;
                                padding: 20px; display: inline-block; min-width: 200px;">
                        <span style="font-size: 36px; font-weight: bold; letter-spacing: 12px; color: #333;">
                            {otp_code}
                        </span>
                    </div>
                </div>
                <p style="color: #999; font-size: 14px;">
                    This code expires in {expiry_minutes} minutes.
                </p>
                <p style="color: #999; font-size: 14px;">
                    If you didn't request this, you can safely ignore this email.
                </p>
            </div>
        </body>
        </html>
        """
        return cls.send_html_email(subject, html_message, [email])

    @classmethod
    def send_password_reset_email(cls, email, otp_code, expiry_minutes):
        """
        Specialized method for sending password reset emails.
        """
        subject = "Reset Your PatNabor Password"
        html_message = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px; text-align: center;">
                <h1 style="color: white; margin: 0;">PatNabor</h1>
            </div>
            <div style="padding: 30px; background: #f9f9f9; border-radius: 0 0 10px 10px;">
                <h2 style="color: #333;">Reset Your Password</h2>
                <p style="color: #666; font-size: 16px;">
                    Use the following code to reset your password:
                </p>
                <div style="text-align: center; margin: 30px 0;">
                    <div style="background: #fff; border: 2px dashed #e74c3c; border-radius: 10px;
                                padding: 20px; display: inline-block; min-width: 200px;">
                        <span style="font-size: 36px; font-weight: bold; letter-spacing: 12px; color: #333;">
                            {otp_code}
                        </span>
                    </div>
                </div>
                <p style="color: #999; font-size: 14px;">
                    This code expires in {expiry_minutes} minutes.
                </p>
                <p style="color: #999; font-size: 14px;">
                    If you didn't request a password reset, please secure your account immediately.
                </p>
            </div>
        </body>
        </html>
        """
        return cls.send_html_email(subject, html_message, [email])
