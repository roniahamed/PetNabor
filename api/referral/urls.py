from django.urls import path

from .views import ReferralDashboardView, ReferralMyView, ReferralTransactionListView

urlpatterns = [
    path("my/", ReferralMyView.as_view(), name="referral-my"),
    path("dashboard/", ReferralDashboardView.as_view(), name="referral-dashboard"),
    path("transactions/", ReferralTransactionListView.as_view(), name="referral-transactions"),
]
