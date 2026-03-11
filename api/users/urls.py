from django.urls import path
from .views import FirebaseLoginView, UserDetailView, NotificationSettingsView



urlpatterns = [
    path('login/firebase/', FirebaseLoginView.as_view(), name='firebase-login'),
    path('user/', UserDetailView.as_view(), name='user-detail'),
    path('user/notification-settings/', NotificationSettingsView.as_view(), name='notification-settings'),
    
]
