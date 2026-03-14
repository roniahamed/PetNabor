from rest_framework import viewsets, permissions
from .models import PetProfile
from .serializers import PetProfileSerializer

class PetProfileViewSet(viewsets.ModelViewSet):
    serializer_class = PetProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PetProfile.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
