from django.contrib import admin
from .models import PetProfile

    
@admin.register(PetProfile)
class PetProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'pet_name', 'pet_type', 'size', 'weight', 'weight_type', 'date_of_birth')
    search_fields = ('user__email', 'user__username', 'pet_name')
    ordering = ('user__id',)
    
