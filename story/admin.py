"""
Admin registration for the Story feature.
"""

from django.contrib import admin

from .models import Story, StoryReaction, StoryReply, StoryView


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = [
        "id", "author", "media_type", "privacy", "views_count",
        "expires_at", "created_at",
    ]
    list_filter = ["media_type", "privacy"]
    search_fields = ["author__email", "author__username", "text_content"]
    readonly_fields = ["id", "views_count", "created_at"]
    raw_id_fields = ["author"]
    date_hierarchy = "created_at"


@admin.register(StoryView)
class StoryViewAdmin(admin.ModelAdmin):
    list_display = ["id", "story", "viewer", "viewed_at"]
    raw_id_fields = ["story", "viewer"]
    readonly_fields = ["id", "viewed_at"]


@admin.register(StoryReaction)
class StoryReactionAdmin(admin.ModelAdmin):
    list_display = ["id", "story", "user", "reaction_type", "created_at"]
    list_filter = ["reaction_type"]
    raw_id_fields = ["story", "user"]
    readonly_fields = ["id", "created_at"]


@admin.register(StoryReply)
class StoryReplyAdmin(admin.ModelAdmin):
    list_display = ["id", "story", "user", "created_at"]
    raw_id_fields = ["story", "user"]
    readonly_fields = ["id", "created_at"]
