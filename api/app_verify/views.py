"""
Views for handling App Verification pricing and RevenueCat webhooks.
"""

import logging
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model

from api.notifications.services import send_notification
from api.notifications.models import NotificationTypes

from .models import VerificationConfig
from .serializers import VerificationConfigSerializer
from django.conf import settings
import os
import requests

logger = logging.getLogger(__name__)
User = get_user_model()


class VerificationConfigView(APIView):
    """
    Returns the current verification price and active status.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        config = VerificationConfig.get_instance()
        serializer = VerificationConfigSerializer(config)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AppVerificationStatusView(APIView):
    """
    Returns the authenticated user's verification status and timeline.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            "is_app_verified": user.is_app_verified,
            "app_verified_at": user.app_verified_at,
            "is_identity_verified": user.is_identity_verified,
            "persona_status": user.persona_status
        }, status=status.HTTP_200_OK)


class RevenueCatWebhookView(APIView):
    """
    Handles RevenueCat webhooks to verify one-time non-consumable purchases.
    Never trust client-side purchase status, always rely on this backend webhook.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            expected_secret = os.getenv("REVENUECAT_WEBHOOK_SECRET")
            if expected_secret:
                auth_header = request.headers.get("Authorization")
                if auth_header != f"Bearer {expected_secret}":
                    logger.warning("RevenueCat webhook: Unauthorized request")
                    return Response({"detail": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

            event = request.data.get("event", {})
            if not event:
                event = request.data

            event_type = event.get("type", "")
            app_user_id = event.get("app_user_id")

            if not app_user_id:
                logger.error("RevenueCat webhook processing failed: Missing app_user_id")
                return Response({"detail": "Missing app_user_id"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                user = User.objects.get(id=app_user_id)
            except User.DoesNotExist:
                logger.error(f"RevenueCat webhook processing failed: User not found for app_user_id={app_user_id}")
                return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)

            SUCCESS_EVENTS = ["INITIAL_PURCHASE", "NON_RENEWING_PURCHASE"]

            if event_type in SUCCESS_EVENTS:
                if not user.is_app_verified:
                    user.is_app_verified = True
                    user.app_verified_at = timezone.now()
                    user.save(update_fields=['is_app_verified', 'app_verified_at'])
                    logger.info(f"User {user.id} successfully app-verified via RevenueCat {event_type}.")
                    
                    send_notification(
                        title="You are now Verified!",
                        body="Your one-time payment was successful and your persona is verified.",
                        user_id=user.id,
                        notification_type=NotificationTypes.SYSTEM,
                        data={"event_type": event_type, "type": "verification_success"}
                    )
                else:
                    logger.info(f"User {user.id} received {event_type} but is already verified.")
                    
            elif event_type == "CANCELLATION":
                user.is_app_verified = False
                user.app_verified_at = None
                user.save(update_fields=['is_app_verified', 'app_verified_at'])
                logger.info(f"User {user.id} app verification revoked via RevenueCat {event_type}.")

            return Response({"status": "received"}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error processing RevenueCat webhook: {e}")
            return Response({"detail": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PersonaInitView(APIView):
    """
    Initializes a Persona Inquiry securely from the backend.
    Takes the authenticated user's ID and securely bounds it to the inquiry as reference_id.
    Ensures that the frontend cannot tamper with the reference_id.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        # SECURITY: Prevent hitting Persona's API (and wasting money) if the user hasn't paid yet!
        if not user.is_app_verified:
            logger.warning(f"User {user.id} tried to init Persona without paying.")
            return Response(
                {"detail": "You must pay for the verification badge before starting the ID scan."}, 
                status=status.HTTP_402_PAYMENT_REQUIRED
            )

        api_key = os.getenv("PERSONA_API_KEY")
        template_id = os.getenv("PERSONA_TEMPLATE_ID")

        if not api_key or not template_id:
            logger.error("Persona setup is incomplete: Missing PERSONA_API_KEY or PERSONA_TEMPLATE_ID")
            return Response(
                {"detail": "Persona configuration is missing on the server."}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        url = "https://withpersona.com/api/v1/inquiries"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Persona-Version": "2023-01-05",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        payload = {
            "data": {
                "attributes": {
                    "template-id": template_id,
                    "reference-id": str(user.id)
                }
            }
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 201:
                data = response.json()
                inquiry_id = data.get("data", {}).get("id")
                
                user.persona_inquiry_id = inquiry_id
                user.persona_status = "pending"
                user.save(update_fields=['persona_inquiry_id', 'persona_status'])
                
                return Response({"inquiry_id": inquiry_id}, status=status.HTTP_201_CREATED)
            else:
                logger.error(f"Persona API Error: {response.text}")
                return Response({"detail": "Failed to initialize Persona inquiry"}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception as e:
            logger.error(f"Exception calling Persona: {e}")
            return Response({"detail": "Server error while communicating with Persona"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


import hmac
import hashlib

class PersonaWebhookView(APIView):
    """
    Handles webhooks specifically from withpersona.com.
    Persona sends inquiry.completed or inquiry.failed webhooks when real KYC finishes.
    """
    permission_classes = [AllowAny]

    def verify_signature(self, signature_header, body_bytes, secret):
        if not signature_header or not secret:
            return False
        try:
            parts = dict(part.split("=") for part in signature_header.split(","))
            t = parts.get("t")
            v1 = parts.get("v1")
            
            payload = f"{t}.".encode('utf-8') + body_bytes
            computed_sig = hmac.new(secret.encode('utf-8'), payload, hashlib.sha256).hexdigest()
            return hmac.compare_digest(v1, computed_sig)
        except Exception as e:
            logger.error(f"Persona signature verification failed parsing: {e}")
            return False

    def post(self, request):
        secret = os.getenv("PERSONA_WEBHOOK_SECRET")
        if secret:
            signature_header = request.headers.get("X-Persona-Signature")
            # For DRF, request.body holds the raw bytes needed for HMAC verification.
            if not self.verify_signature(signature_header, request.body, secret):
                logger.warning("Persona webhook: Invalid or missing X-Persona-Signature")
                return Response({"detail": "Invalid signature"}, status=status.HTTP_403_FORBIDDEN)

        try:
            event = request.data.get("data", {})
            event_attributes = event.get("attributes", {})
            event_name = event_attributes.get("name", "")
            
            payload_data = event_attributes.get("payload", {}).get("data", {})
            inquiry_id = payload_data.get("id")
            inquiry_attributes = payload_data.get("attributes", {})
            
            app_user_id = inquiry_attributes.get("reference_id")
            new_status = inquiry_attributes.get("status")

            if not app_user_id:
                logger.warning("Persona webhook: Missing reference_id (app_user_id)")
                return Response({"status": "no reference_id"}, status=status.HTTP_200_OK)

            try:
                user = User.objects.get(id=app_user_id)
            except User.DoesNotExist:
                logger.error(f"Persona webhook: User not found for reference_id={app_user_id}")
                return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)

            if event_name in ["inquiry.completed", "inquiry.approved"]:
                user.is_identity_verified = True
                user.persona_status = "approved"
                user.persona_inquiry_id = inquiry_id
                user.save(update_fields=['is_identity_verified', 'persona_status', 'persona_inquiry_id'])
                logger.info(f"User {user.id} identity successfully verified via Persona.")
                
                send_notification(
                    title="ID Verification Successful!",
                    body="Your ID documents have been approved by Persona.",
                    user_id=user.id,
                    notification_type=NotificationTypes.SYSTEM,
                    data={"type": "persona_success"}
                )
            
            elif event_name in ["inquiry.failed", "inquiry.declined"]:
                user.is_identity_verified = False
                user.persona_status = "declined"
                user.persona_inquiry_id = inquiry_id
                user.save(update_fields=['is_identity_verified', 'persona_status', 'persona_inquiry_id'])
                logger.info(f"User {user.id} identity verification failed via Persona.")

            return Response({"status": "received"}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error processing Persona webhook: {e}")
            return Response({"detail": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

