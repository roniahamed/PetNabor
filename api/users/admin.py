from django.contrib import admin
from .models import User, Profile, NotificationSettings, PetProfile
from django.utils.html import format_html



@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id',  'email', 'is_staff', 'is_active', 'created_at')
    list_filter = ('is_staff', 'is_active')
    search_fields = ('username', 'email')
    ordering = ('id',)
    
    
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'bio', 'profile_picture')
    search_fields = ('user__email', 'user__username')
    ordering = ('user__id',)
    
    def profile_picture(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" />', obj.image.url)
        return '-'
    profile_picture.short_description = 'Profile Picture'   
    
@admin.register(NotificationSettings)
class NotificationSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'email_notifications', 'push_notifications')
    search_fields = ('user__email', 'user__username')
    ordering = ('user__id',)
    
@admin.register(PetProfile)
class PetProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'pet_name', 'pet_type', 'size', 'weight', 'weight_type', 'date_of_birth')
    search_fields = ('user__email', 'user__username', 'pet_name')
    ordering = ('user__id',)
    
