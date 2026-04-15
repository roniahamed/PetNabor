from django.urls import path
from .views import RevenueCatWebhookView, VerificationConfigView, AppVerificationStatusView, PersonaWebhookView, PersonaInitView

urlpatterns = [
    path("config/", VerificationConfigView.as_view(), name="verification-config"),
    path("status/", AppVerificationStatusView.as_view(), name="verification-status"),
    path("persona-init/", PersonaInitView.as_view(), name="persona-init"),
    path("webhook/", RevenueCatWebhookView.as_view(), name="revenuecat-webhook"),
    path("persona-webhook/", PersonaWebhookView.as_view(), name="persona-webhook"),
]
