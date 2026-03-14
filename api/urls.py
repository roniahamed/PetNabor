from django.urls import path, include



urlpatterns = [
    path('users/', include('api.users.urls')),
    path('notifications/', include('api.notifications.urls')),
    path('pets/', include('api.pet.urls')),  
]