from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from .serializers import NotificationSettingsSerializer
from .models import NotificationSettings




class NotificationSettingsView(RetrieveUpdateAPIView):
    serializer_class = NotificationSettingsSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        obj, created = NotificationSettings.objects.get_or_create(user=self.request.user)
        return obj