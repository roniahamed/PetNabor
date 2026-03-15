from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FriendRequestViewSet,
    BlockUserView,
    UserSearchView,
    FriendListView,
    UnfriendView,
)

router = DefaultRouter()
router.register(r'requests', FriendRequestViewSet, basename='friend-requests')

urlpatterns = [
    path('', include(router.urls)),
    path('block/', BlockUserView.as_view(), name='block-user'),
    path('search/', UserSearchView.as_view(), name='search-users'),
    path('list/', FriendListView.as_view(), name='list-friends'),
    path('remove/', UnfriendView.as_view(), name='remove-friend'),
]
