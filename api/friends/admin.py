from django.contrib import admin
from .models import FriendRequest, Friendship, UserBlock


@admin.register(FriendRequest)
class FriendRequestAdmin(admin.ModelAdmin):
    list_display = ("sender", "receiver", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("sender__username", "receiver__username")


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ("sender", "receiver", "created_at")
    list_filter = ("created_at",)
    search_fields = ("sender__username", "receiver__username")


@admin.register(UserBlock)
class UserBlockAdmin(admin.ModelAdmin):
    list_display = ("blocker", "blocked_user", "created_at")
    list_filter = ("created_at",)
    search_fields = ("blocker__username", "blocked_user__username")
