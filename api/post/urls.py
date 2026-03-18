"""
URL routing for the Post app.
Uses DefaultRouter for standard RESTful viewsets.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    PostViewSet, PostCommentViewSet, 
    SavedPostViewSet
)

router = DefaultRouter()
router.register(r'posts', PostViewSet, basename='post')
router.register(r'comments', PostCommentViewSet, basename='comment')
router.register(r'saved-posts', SavedPostViewSet, basename='saved-post')

urlpatterns = [
    path('', include(router.urls)),
]
