from django.contrib import admin
from .models import User, Profile
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

