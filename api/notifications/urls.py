"""
URL patterns for the notifications API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationSettingsView, FCMDeviceView, NotificationViewSet

router = DefaultRouter()
router.register(r"", NotificationViewSet, basename="notifications")


urlpatterns = [
    path("notifications/", include(router.urls)),
    path(
        "notification-settings/",
        NotificationSettingsView.as_view(),
        name="notification-settings",
    ),
    path("fcm-devices/", FCMDeviceView.as_view(), name="fcm-devices"),
]
