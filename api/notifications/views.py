from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.decorators import action 
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from .paginations import NotificationPagination

from .serializers import NotificationSettingsSerializer, FCMDeviceSerializer, NotificationSerializer, UserNotificationSettingsSerializer
from .models import NotificationSettings, FCMDevice, Notifications

class NotificationSettingsView(RetrieveUpdateAPIView):
    serializer_class = NotificationSettingsSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        obj, created = NotificationSettings.objects.get_or_create(user=self.request.user)
        return obj

class FCMDeviceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        devices = FCMDevice.objects.filter(user=request.user)
        serializer = FCMDeviceSerializer(devices, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        serializer = FCMDeviceSerializer(data=request.data)

        if serializer.is_valid():

            registration_id = serializer.validated_data['registration_id']

            obj, created = FCMDevice.objects.update_or_create(
                registration_id=registration_id,
                defaults={
                    'user': request.user,
                }
            )
            if created:
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.data, status=status.HTTP_200_OK)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request):
        registration_id = request.data.get('registration_id')
        if not registration_id:
            return Response({'error': 'registration_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            device = FCMDevice.objects.get(registration_id=registration_id, user=request.user)
            device.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except FCMDevice.DoesNotExist:
            return Response({'error': 'Device not found'}, status=status.HTTP_404_NOT_FOUND)
        

class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NotificationPagination

    def get_queryset(self):
        return Notifications.objects.filter(user=self.request.user).order_by('-created_at')
    
    # def list(self, request, *args, **kwargs):
    #     queryset = self.get_queryset()
    #     serializer = self.get_serializer(queryset, many=True)
    #     return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({'status': 'all notifications marked as read'})

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.save()
        return Response({'status': 'notification marked as read'})
    