from django.urls import path
from .views import FirebaseLoginView, UserDetailView, ProfileDetailView


urlpatterns = [
    path("login/firebase/", FirebaseLoginView.as_view(), name="firebase-login"),
    path("user/", UserDetailView.as_view(), name="user-detail"),
    path("profile/", ProfileDetailView.as_view(), name="profile-detail"),
]
