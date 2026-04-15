from django.urls import path
from .views import RevenueCatWebhookView, VerificationConfigView, AppVerificationStatusView

urlpatterns = [
    path("config/", VerificationConfigView.as_view(), name="verification-config"),
    path("status/", AppVerificationStatusView.as_view(), name="verification-status"),
    path("webhook/", RevenueCatWebhookView.as_view(), name="revenuecat-webhook"),
]
