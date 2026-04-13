from django.urls import path
from .views import SiteSettingsAPIView

urlpatterns = [
    path('', SiteSettingsAPIView.as_view(), name='global-settings'),
]
