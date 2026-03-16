"""
Messaging admin — ChatThread, ThreadParticipant, Message.
"""

from django.contrib import admin

from .models import ChatThread, Message, ThreadParticipant


class ThreadParticipantInline(admin.TabularInline):
    model = ThreadParticipant
    extra = 0
    fields = ["user", "role", "is_muted", "joined_at", "left_at"]
    readonly_fields = ["joined_at"]


@admin.register(ChatThread)
class ChatThreadAdmin(admin.ModelAdmin):
    list_display = [
        "id", "thread_type", "name", "created_by",
        "last_message_timestamp", "created_at",
    ]
    list_filter = ["thread_type"]
    search_fields = ["name", "created_by__email", "created_by__username"]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [ThreadParticipantInline]


@admin.register(ThreadParticipant)
class ThreadParticipantAdmin(admin.ModelAdmin):
    list_display = ["id", "thread", "user", "role", "is_muted", "joined_at", "left_at"]
    list_filter = ["role", "is_muted"]
    search_fields = ["user__email", "user__username"]
    readonly_fields = ["id", "joined_at"]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = [
        "id", "thread", "sender", "message_type",
        "is_deleted_for_everyone", "is_read", "created_at",
    ]
    list_filter = ["message_type", "is_deleted_for_everyone", "is_read"]
    search_fields = ["sender__email", "sender__username", "text_content"]
    readonly_fields = ["id", "created_at", "updated_at"]
