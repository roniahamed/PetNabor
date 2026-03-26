from django.contrib import admin
from .models import Meeting, MeetingFeedback

@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'receiver', 'visit_date', 'visit_time', 'reason', 'status', 'created_at')
    list_filter = ('status', 'reason', 'visit_date')
    search_fields = ('sender__username', 'receiver__username', 'visitor_name')

@admin.register(MeetingFeedback)
class MeetingFeedbackAdmin(admin.ModelAdmin):
    list_display = ('id', 'meeting', 'reviewer', 'reviewee', 'rating', 'is_public', 'created_at')
    list_filter = ('is_public', 'rating')
    search_fields = ('reviewer__username', 'reviewee__username', 'meeting__id')
