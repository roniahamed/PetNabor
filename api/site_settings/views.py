from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .models import SiteSettings
from .serializers import SiteSettingsSerializer

class SiteSettingsAPIView(APIView):
    """
    Returns the global site settings used for the frontend application.
    This is read-only for public access.
    """
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        settings = SiteSettings.get_instance()
        serializer = SiteSettingsSerializer(settings)
        return Response(serializer.data)
