from rest_framework import viewsets, permissions
from rest_framework.exceptions import PermissionDenied
from .models import Vendor
from .serializers import VendorSerializer
from .permissions import IsVendorUser, IsOwnerOrReadOnly

class VendorViewSet(viewsets.ModelViewSet):
    serializer_class = VendorSerializer
    permission_classes = [permissions.IsAuthenticated, IsVendorUser, IsOwnerOrReadOnly]
    queryset = Vendor.objects.all()
    
    def perform_create(self, serializer):
        # Additional safety check
        if self.request.user.user_type != 'vendor' and self.request.user.user_type != 'admin':
            raise PermissionDenied("Only vendor accounts can create a vendor profile.")
        serializer.save(user=self.request.user)
