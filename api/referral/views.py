"""
Referral views.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Q, Sum
from rest_framework import status, serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter, OpenApiTypes

from .models import ReferralSettings, ReferralTransaction, TransactionStatus
from .serializers import (
    ReferralMemberSerializer, 
    ReferralTransactionSerializer,
    ReferralCodeVerifySerializer,
    ReferralCodeRedeemSerializer,
)
from .services import get_or_create_wallet

User = get_user_model()


def _total_earned(wallet):
    return (
        ReferralTransaction.objects.filter(
            wallet=wallet,
            amount__gt=0,
            status=TransactionStatus.COMPLETED,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )


class ReferralMyView(APIView):
    """
    GET /api/referral/my/
    Returns the current user's referral code and quick stats.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: inline_serializer(
            name='ReferralMyResponse',
            fields={
                'referral_code': serializers.CharField(),
                'referrer_points': serializers.IntegerField(),
                'referee_points': serializers.IntegerField(),
                'balance': serializers.DecimalField(max_digits=12, decimal_places=2),
                'total_earned': serializers.DecimalField(max_digits=12, decimal_places=2),
                'joined_count': serializers.IntegerField(),
            }
        )}
    )
    def get(self, request):
        user = request.user
        try:
            profile = user.profile
        except Exception:
            return Response({"detail": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)

        wallet = get_or_create_wallet(user)
        cfg = ReferralSettings.get_instance()

        return Response({
            "referral_code": profile.referral_code,
            "referrer_points": cfg.referrer_points,
            "referee_points": cfg.referee_points,
            "balance": wallet.balance,
            "total_earned": _total_earned(wallet),
            "joined_count": User.objects.filter(profile__referred_by=user).count(),
        })


class ReferralDashboardView(APIView):
    """
    GET /api/referral/dashboard/?q=<search>
    Full dashboard: stats + member list (optional search by name/email).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter('q', OpenApiTypes.STR, description='Search by name or email'),
        ],
        responses={200: inline_serializer(
            name='ReferralDashboardResponse',
            fields={
                'referral_code': serializers.CharField(),
                'balance': serializers.DecimalField(max_digits=12, decimal_places=2),
                'total_earned': serializers.DecimalField(max_digits=12, decimal_places=2),
                'joined_count': serializers.IntegerField(),
                'members': ReferralMemberSerializer(many=True),
            }
        )}
    )
    def get(self, request):
        user = request.user
        try:
            profile = user.profile
        except Exception:
            return Response({"detail": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)

        wallet = get_or_create_wallet(user)
        joined_total = User.objects.filter(profile__referred_by=user).count()

        members_qs = User.objects.filter(profile__referred_by=user).select_related("profile")
        search = request.query_params.get("q", "").strip()
        if search:
            members_qs = members_qs.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(email__icontains=search)
            )

        members_data = ReferralMemberSerializer(
            members_qs, many=True, context={"request": request}
        ).data

        return Response({
            "referral_code": profile.referral_code,
            "balance": wallet.balance,
            "total_earned": _total_earned(wallet),
            "joined_count": joined_total,
            "members": members_data,
        })


class TransactionPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class ReferralTransactionListView(APIView):
    """
    GET /api/referral/transactions/
    Paginated transaction history for the current user.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses=ReferralTransactionSerializer(many=True),
    )
    def get(self, request):
        wallet = get_or_create_wallet(request.user)
        qs = ReferralTransaction.objects.filter(wallet=wallet).order_by("-created_at")
        paginator = TransactionPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = ReferralTransactionSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class ReferralVerifyView(APIView):
    """
    POST /api/referral/verify/
    Verify if a referral code is valid.
    """
    permission_classes = []

    @extend_schema(
        request=ReferralCodeVerifySerializer,
        responses={200: inline_serializer(
            name='ReferralVerifyResponse',
            fields={
                'valid': serializers.BooleanField(),
                'referrer_name': serializers.CharField(),
            }
        )}
    )
    def post(self, request):
        serializer = ReferralCodeVerifySerializer(data=request.data)
        if not serializer.is_valid():
            errors = getattr(serializer, "errors", {})
            first_error = next(iter(errors.values()))[0] if errors else "Invalid referral code."
            return Response({"success": False, "message": str(first_error)}, status=status.HTTP_400_BAD_REQUEST)
            
        profile = serializer.validated_data["code"]
        
        name = f"{profile.user.first_name} {profile.user.last_name}".strip()
        if not name:
            name = profile.user.email.split("@")[0] if profile.user.email else "User"

        return Response({
            "valid": True,
            "referrer_name": name,
        })


class ReferralRedeemView(APIView):
    """
    POST /api/referral/redeem/
    Redeem a code manually for a logged-in user who hasn't redeemed one yet.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ReferralCodeRedeemSerializer,
        responses={200: inline_serializer(
            name='ReferralRedeemResponse',
            fields={
                'message': serializers.CharField(),
            }
        )}
    )
    def post(self, request):
        serializer = ReferralCodeRedeemSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            errors = getattr(serializer, "errors", {})
            first_error = next(iter(errors.values()))[0] if errors else "Invalid referral code."
            return Response({"success": False, "message": str(first_error)}, status=status.HTTP_400_BAD_REQUEST)
            
        referrer_profile = serializer.validated_data["code"]
        
        profile = request.user.profile
        profile.referred_by = referrer_profile.user
        profile.save(update_fields=["referred_by"])

        # Awarding of points usually triggered by signal, but we can explicitly call the task just in case
        # However, the signal on_profile_saved will be fired automatically when referred_by is set,
        # which calls award_referral_points_task.delay(request.user.id). 
        # So we don't need to double-trigger here.

        return Response({
            "message": "Referral code redeemed successfully.",
        })
