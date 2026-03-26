from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import MeetingViewSet, MeetingFeedbackViewSet

router = DefaultRouter()
router.register(r'requests', MeetingViewSet, basename='meeting')
router.register(r'feedback', MeetingFeedbackViewSet, basename='meeting-feedback')

urlpatterns = [
    path('', include(router.urls)),
]
