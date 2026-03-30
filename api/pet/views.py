from rest_framework import viewsets, generics, permissions
from .models import PetProfile
from .serializers import PetProfileSerializer


class PetProfileViewSet(viewsets.ModelViewSet):
    serializer_class = PetProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PetProfile.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        pet = serializer.save(user=self.request.user)
        if "image" in self.request.FILES:
            from .tasks import process_pet_image_task

            process_pet_image_task.delay(str(pet.id))

    def perform_update(self, serializer):
        pet = serializer.save()
        if "image" in self.request.FILES:
            from .tasks import process_pet_image_task

            process_pet_image_task.delay(str(pet.id))


class UserPetListView(generics.ListAPIView):
    """
    GET /pets/user/<uuid:user_id>/pets/
    Public (authenticated) — returns the pet list of any user.
    """
    serializer_class = PetProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user_id = self.kwargs["user_id"]
        return PetProfile.objects.filter(user_id=user_id).order_by("pet_name")
