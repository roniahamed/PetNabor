from .models import Categories, Brand, Product
from .serializers import CategorySerializer, BrandSerializer, ProductSerializer
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from .permissions import IsStaffOrReadOnly, IsVendorOrReadOnly
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from rest_framework import status
from django_filters.rest_framework import DjangoFilterBackend

from paginations.cursor_pagination import StandardCursorPagination

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Categories.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsStaffOrReadOnly]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['name']
    filterset_fields = ['name']
    
class BrandViewSet(viewsets.ModelViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    permission_classes = [IsStaffOrReadOnly]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['name']
    filterset_fields = ['name']

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsVendorOrReadOnly]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['name', 'description']
    filterset_fields = ['category', 'brand', 'vendor']
    ordering_fields = ['price', 'created_at']
    ordering = ['-created_at']
    pagination_class = StandardCursorPagination

    def get_queryset(self):
        # Order by vendor plan priority first, then by the default orderings
        return Product.objects.all().order_by('-vendor__plan__has_category_top_slot', '-created_at')

    def perform_create(self, serializer):
        vendor = self.request.user.vendor_profiles.first()
        if not vendor:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You must be a vendor to create products.")

        # Check vendor plan product limit
        active_plan = vendor.plan
        if active_plan:
            max_products = active_plan.max_products
            if max_products > 0:
                current_count = Product.objects.filter(vendor=vendor, is_active=True).count()
                if current_count >= max_products:
                    from rest_framework.exceptions import ValidationError
                    raise ValidationError({'detail': f'Product limit ({max_products}) reached for your current plan.'})

        serializer.save(vendor=vendor)
    
    @action(detail=True, methods=['post'], permission_classes=[IsVendorOrReadOnly])
    def deactivate(self, request, pk=None):
        product = get_object_or_404(Product, pk=pk)
        if product.vendor != request.user.vendor:
            return Response({'detail': 'Not authorized to deactivate this product.'}, status=status.HTTP_403_FORBIDDEN)
        product.is_active = False
        product.save()
        return Response({'detail': 'Product deactivated successfully.'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], permission_classes=[IsVendorOrReadOnly])
    def activate(self, request, pk=None):
        product = get_object_or_404(Product, pk=pk)
        if product.vendor != request.user.vendor:
            return Response({'detail': 'Not authorized to activate this product.'}, status=status.HTTP_403_FORBIDDEN)
        product.is_active = True
        product.save()
        return Response({'detail': 'Product activated successfully.'}, status=status.HTTP_200_OK)
    
    
