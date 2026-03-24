from django.contrib import admin
from .models import BlogCategory, Blog, BlogLike, BlogComment, BlogViewTracker

@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'category', 'is_published', 'created_at', 'views_count', 'likes_count')
    list_filter = ('is_published', 'is_deleted', 'category', 'created_at')
    search_fields = ('title', 'author__username', 'author__email', 'tags')
    raw_id_fields = ('author',)
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('author', 'category', 'title', 'slug', 'content_body', 'cover_image')
        }),
        ('SEO & Metadata', {
            'fields': ('meta_title', 'meta_description', 'tags')
        }),
        ('Status', {
            'fields': ('is_published', 'published_at', 'is_deleted')
        }),
        ('Counters (Read-Only)', {
            'fields': ('views_count', 'likes_count', 'comments_count', 'shares_count'),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ('views_count', 'likes_count', 'comments_count', 'shares_count')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(BlogLike)
class BlogLikeAdmin(admin.ModelAdmin):
    list_display = ('blog', 'user', 'created_at')
    raw_id_fields = ('blog', 'user')


@admin.register(BlogComment)
class BlogCommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'blog', 'user', 'is_edited', 'is_deleted', 'created_at')
    list_filter = ('is_edited', 'is_deleted', 'created_at')
    raw_id_fields = ('blog', 'user', 'parent_comment')
    search_fields = ('comment_text', 'user__username', 'blog__title')


@admin.register(BlogViewTracker)
class BlogViewTrackerAdmin(admin.ModelAdmin):
    list_display = ('blog', 'user', 'ip_address', 'created_at')
    raw_id_fields = ('blog', 'user')
    search_fields = ('ip_address', 'blog__title')
