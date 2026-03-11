from django.urls import path
from .views import FirebaseLoginView



urlpatterns = [
    path('login/firebase/', FirebaseLoginView.as_view(), name='firebase-login'),
]
