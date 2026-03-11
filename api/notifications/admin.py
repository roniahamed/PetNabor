from django.contrib import admin
from .models import NotificationSettings


    
@admin.register(NotificationSettings)
class NotificationSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'email_notifications', 'push_notifications')
    search_fields = ('user__email', 'user__username')
    ordering = ('user__id',)