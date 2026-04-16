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
    def send_otp_email(cls, email, otp_code, expiry_minutes, subject="Your PetNabor Verification Code"):
        """
        Specialized method for sending OTP emails with PetNabor branding.
        """
        html_message = f"""
        <!DOCTYPE html>
            <html lang="en">
            <body style="margin: 0; padding: 0; background-color: #f4f4f4; font-family: Arial, sans-serif;">
            
            <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f4f4f4; padding: 30px 0;">
            <tr>
            <td align="center">
            <table width="520" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; border: 1px solid #e0e0e0;">
            
                    <!-- Header: Logo -->
            <tr>
            <td style="padding: 20px 30px 16px 30px; border-bottom: 1px solid #eeeeee;">
            <img src="https://res.cloudinary.com/dicqtpu0g/image/upload/v1776276079/logo.png_3_gr4tnd.png" alt="PetNabor" style="height: 48px; display: block;" />
            </td>
            </tr>
            
                    <!-- Body -->
            <tr>
            <td style="padding: 30px 30px 10px 30px;">
            <h2 style="margin: 0 0 20px 0; font-size: 18px; font-weight: bold; color: #222222; text-align: center;">
                            Your PetNabor Verification Code
            </h2>
            
                        <p style="margin: 0 0 6px 0; font-size: 15px; color: #333333;">Hi there,</p>
            <p style="margin: 0 0 24px 0; font-size: 15px; color: #333333; line-height: 1.5;">
                            Please use the 4-digit code below to verify your email address for PetNabor.
            </p>
            
                        <!-- OTP Box -->
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 24px;">
            <tr>
            <td align="center">
            <table cellpadding="0" cellspacing="0">
            <tr>
            <td style="border: 1px solid #cccccc; border-radius: 4px; padding: 10px 24px;">
            <span style="font-size: 22px; font-weight: bold; color: #222222; letter-spacing: 4px;">
                                        {otp_code}
            </span>
            </td>
            </tr>
            </table>
            </td>
            </tr>
            </table>
            
                        <p style="margin: 0 0 16px 0; font-size: 14px; color: #444444; line-height: 1.6;">
                            This code expires in {expiry_minutes} minutes. If you didn't request this, you can safely ignore this email.
            </p>
            
                        <p style="margin: 0; font-size: 14px; color: #333333; line-height: 1.6;">
                            Thank you,<br>
                            The PetNabor team
            </p>
            </td>
            </tr>
            
                    <!-- Footer spacer -->
            <tr>
            <td style="padding: 20px 30px;">
            </td>
            </tr>
            
                    </table>
            </td>
            </tr>
            </table>
            
            </body>
            </html>
        """
        return cls.send_html_email(subject, html_message, [email])

    @classmethod
    def send_password_reset_email(cls, email, otp_code, expiry_minutes):
        """
        Specialized method for sending password reset emails.
        """
        subject = "Reset Your PetNabor Password"
        html_message = f"""
        <!DOCTYPE html>
            <html lang="en">
            <body style="margin: 0; padding: 0; background-color: #f4f4f4; font-family: Arial, sans-serif;">
            
            <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f4f4f4; padding: 30px 0;">
            <tr>
            <td align="center">
            <table width="520" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; border: 1px solid #e0e0e0;">
            
                    <!-- Header: Logo -->
            <tr>
            <td style="padding: 20px 30px 16px 30px; border-bottom: 1px solid #eeeeee;">
            <img src="https://res.cloudinary.com/dicqtpu0g/image/upload/v1776276079/logo.png_3_gr4tnd.png" alt="PetNabor" style="height: 48px; display: block;" />
            </td>
            </tr>
            
                    <!-- Body -->
            <tr>
            <td style="padding: 30px 30px 10px 30px;">
            <h2 style="margin: 0 0 20px 0; font-size: 18px; font-weight: bold; color: #222222; text-align: center;">
                            Reset Your Password
            </h2>
            
                        <p style="margin: 0 0 6px 0; font-size: 15px; color: #333333;">Hi there,</p>
            <p style="margin: 0 0 24px 0; font-size: 15px; color: #333333; line-height: 1.5;">
                            Use the following code to reset your password for PetNabor.
            </p>
            
                        <!-- OTP Box -->
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 24px;">
            <tr>
            <td align="center">
            <table cellpadding="0" cellspacing="0">
            <tr>
            <td style="border: 1px solid #cccccc; border-radius: 4px; padding: 10px 24px;">
            <span style="font-size: 22px; font-weight: bold; color: #222222; letter-spacing: 4px;">
                                        {otp_code}
            </span>
            </td>
            </tr>
            </table>
            </td>
            </tr>
            </table>
            
                        <p style="margin: 0 0 16px 0; font-size: 14px; color: #444444; line-height: 1.6;">
                            This code expires in {expiry_minutes} minutes. If you didn't request a password reset, please secure your account immediately.
            </p>
            
                        <p style="margin: 0; font-size: 14px; color: #333333; line-height: 1.6;">
                            Thank you,<br>
                            The PetNabor team
            </p>
            </td>
            </tr>
            
                    <!-- Footer spacer -->
            <tr>
            <td style="padding: 20px 30px;"></td>
            </tr>
            
                    </table>
            </td>
            </tr>
            </table>
            
            </body>
            </html>
        """
        return cls.send_html_email(subject, html_message, [email])
