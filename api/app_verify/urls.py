from django.urls import path
from .views import RevenueCatWebhookView, VerificationConfigView, AppVerificationStatusView, PersonaWebhookView

urlpatterns = [
    path("config/", VerificationConfigView.as_view(), name="verification-config"),
    path("status/", AppVerificationStatusView.as_view(), name="verification-status"),
    path("webhook/", RevenueCatWebhookView.as_view(), name="revenuecat-webhook"),
    path("persona-webhook/", PersonaWebhookView.as_view(), name="persona-webhook"),
]
