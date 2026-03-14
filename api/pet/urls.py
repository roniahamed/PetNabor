from rest_framework.routers import DefaultRouter
from .views import PetProfileViewSet

router = DefaultRouter()
router.register(r'pet', PetProfileViewSet, basename='pet')

urlpatterns = router.urls
