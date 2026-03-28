from django.urls import path

from .views import (
    ReferralDashboardView, 
    ReferralMyView, 
    ReferralTransactionListView,
    ReferralVerifyView,
    ReferralRedeemView,
)

urlpatterns = [
    path("my/", ReferralMyView.as_view(), name="referral-my"),
    path("dashboard/", ReferralDashboardView.as_view(), name="referral-dashboard"),
    path("transactions/", ReferralTransactionListView.as_view(), name="referral-transactions"),
    path("verify/", ReferralVerifyView.as_view(), name="referral-verify"),
    path("redeem/", ReferralRedeemView.as_view(), name="referral-redeem"),
]
