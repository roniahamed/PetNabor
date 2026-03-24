from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import PetProfileViewSet, UserPetListView

router = DefaultRouter()
router.register(r'pet', PetProfileViewSet, basename='pet')

urlpatterns = router.urls + [
    path('user/<uuid:user_id>/pets/', UserPetListView.as_view(), name='user-pet-list'),
]
