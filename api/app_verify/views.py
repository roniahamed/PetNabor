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
            "app_verified_at": user.app_verified_at
        }, status=status.HTTP_200_OK)


class RevenueCatWebhookView(APIView):
    """
    Handles RevenueCat webhooks to verify one-time non-consumable purchases.
    Never trust client-side purchase status, always rely on this backend webhook.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        try:
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
