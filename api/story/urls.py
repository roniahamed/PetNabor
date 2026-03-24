"""
URL routing for the Story app.
Single DefaultRouter for StoryViewSet — interaction actions hang off it.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import StoryViewSet

router = DefaultRouter()
router.register(r"stories", StoryViewSet, basename="story")

urlpatterns = [
    path("", include(router.urls)),
]
