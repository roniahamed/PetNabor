import os
import uuid
from django.db import models
from django.conf import settings
from django.utils.text import slugify

# ──────────────────────────────────────────────
# Helper Functions
# ──────────────────────────────────────────────

def blog_cover_path(instance, filename):
    """Generate a collision-resistant UUID-based path for blog covers."""
    _, ext = os.path.splitext(filename)
    unique_filename = f"{uuid.uuid4().hex}{ext.lower()}"
    return os.path.join(f"blogs/{instance.id}/", unique_filename)

def blog_comment_media_path(instance, filename):
    _, ext = os.path.splitext(filename)
    unique_filename = f"{uuid.uuid4().hex}{ext.lower()}"
    return os.path.join(f"blog_comments/{instance.id}/", unique_filename)

# ──────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────

class BlogCategory(models.Model):
    """Categories for organizing blog posts."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, db_index=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Blog Categories"
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Blog(models.Model):
    """Core Blog model for rich-text articles."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='blogs', on_delete=models.CASCADE)
    category = models.ForeignKey(BlogCategory, related_name='blogs', on_delete=models.SET_NULL, null=True, blank=True)

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    content_body = models.TextField(help_text="Markdown or HTML content")
    cover_image = models.FileField(upload_to=blog_cover_path, max_length=500, null=True, blank=True)

    # SEO & meta
    meta_title = models.CharField(max_length=100, null=True, blank=True)
    meta_description = models.CharField(max_length=255, null=True, blank=True)
    tags = models.JSONField(default=list, blank=True, help_text="List of string tags for simple searching")

    # Publishing and deletion states
    is_published = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False, db_index=True)  # Soft delete

    # Denormalized Counters
    views_count = models.PositiveIntegerField(default=0)
    likes_count = models.PositiveIntegerField(default=0)
    comments_count = models.PositiveIntegerField(default=0)
    shares_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_published', 'created_at']),
            models.Index(fields=['slug']),
            models.Index(fields=['author', 'is_published']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Blog.objects.filter(slug=slug).exclude(id=self.id).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Blog: {self.title}"


class BlogLike(models.Model):
    """Tracks User likes on Blogs to prevent duplicate likes."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    blog = models.ForeignKey(Blog, related_name='likes', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='blog_likes', on_delete=models.CASCADE)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('blog', 'user')
        indexes = [
            models.Index(fields=['blog', 'user']),
        ]

    def __str__(self):
        return f"{self.user} liked {self.blog.slug}"


class BlogComment(models.Model):
    """Model for nested blog replies."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    blog = models.ForeignKey(Blog, related_name='comments', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='blog_comments', on_delete=models.CASCADE)
    
    parent_comment = models.ForeignKey('self', null=True, blank=True, related_name='replies', on_delete=models.CASCADE)
    
    comment_text = models.TextField(help_text="Comment body text")
    media_file = models.FileField(upload_to=blog_comment_media_path, max_length=500, null=True, blank=True)

    # Denormalization
    replies_count = models.PositiveIntegerField(default=0)
    
    # Flags
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)  # Soft delete

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['blog', 'parent_comment', 'created_at']),
        ]

    def __str__(self):
        return f"Comment by {self.user} on {self.blog.id}"


class BlogViewTracker(models.Model):
    """Used for tracking unique views. DB fallback if Redis sync fails or for permanent records."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    blog = models.ForeignKey(Blog, related_name='view_tracks', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Helps prevent inserting multiple view logs fast from the same IP
        indexes = [
            models.Index(fields=['blog', 'ip_address']),
            models.Index(fields=['blog', 'user']),
        ]

    def __str__(self):
        return f"View for {self.blog.id} by IP:{self.ip_address} User:{self.user_id}"
