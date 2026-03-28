"""
Referral views.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Q, Sum
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ReferralSettings, ReferralTransaction, TransactionStatus
from .serializers import ReferralMemberSerializer, ReferralTransactionSerializer
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

    def get(self, request):
        wallet = get_or_create_wallet(request.user)
        qs = ReferralTransaction.objects.filter(wallet=wallet).order_by("-created_at")
        paginator = TransactionPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = ReferralTransactionSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
