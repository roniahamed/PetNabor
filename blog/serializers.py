from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import BlogCategory, Blog, BlogLike, BlogComment

User = get_user_model()


class AuthorBasicSerializer(serializers.ModelSerializer):
    """Lightweight user embedding — avoids N+1 and data leakage."""
    profile_picture = serializers.ImageField(source='profile.profile_picture', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'username', 'profile_picture']




class BlogCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogCategory
        fields = ['id', 'name', 'slug']


class BlogListSerializer(serializers.ModelSerializer):
    """Optimized serializer for list views."""
    author = AuthorBasicSerializer(read_only=True)
    category = BlogCategorySerializer(read_only=True)

    class Meta:
        model = Blog
        fields = [
            'id', 'title', 'slug', 'cover_image', 'author', 'category',
            'is_published', 'published_at', 'views_count', 'likes_count',
            'comments_count', 'created_at'
        ]


class BlogDetailSerializer(serializers.ModelSerializer):
    """Full detail serializer with SEO and tags."""
    author = AuthorBasicSerializer(read_only=True)
    category = BlogCategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=BlogCategory.objects.all(), source='category', write_only=True, required=False
    )
    is_liked = serializers.SerializerMethodField()

    class Meta:
        model = Blog
        fields = [
            'id', 'title', 'slug', 'content_body', 'cover_image',
            'author', 'category', 'category_id', 'meta_title', 'meta_description', 
            'tags', 'is_published', 'published_at',
            'views_count', 'likes_count', 'comments_count', 'shares_count',
            'created_at', 'updated_at', 'is_liked'
        ]
        read_only_fields = ['id', 'slug', 'views_count', 'likes_count', 'comments_count', 'shares_count', 'author']

    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # We assume a prefetch or annotation can be used, but safely fallback to exists()
            if hasattr(obj, 'is_liked_by_user'):
                return obj.is_liked_by_user
            return BlogLike.objects.filter(blog=obj, user=request.user).exists()
        return False


class BlogCommentSerializer(serializers.ModelSerializer):
    """Serializer for blog comments, handling nested replies carefully."""
    user = AuthorBasicSerializer(read_only=True)
    reply_count = serializers.IntegerField(source='replies_count', read_only=True)
    replies = serializers.SerializerMethodField()
    
    class Meta:
        model = BlogComment
        fields = [
            'id', 'blog', 'user', 'parent_comment', 'comment_text',
            'media_file', 'reply_count', 'is_edited', 'created_at', 'updated_at', 'replies'
        ]
        read_only_fields = ['id', 'blog', 'user', 'reply_count', 'is_edited']

    def get_replies(self, obj):
        # Only fetch replies if this is a top-level comment to strictly avoid deep N+1.
        # Can scale via cursor pagination for replies instead of full nesting.
        if obj.parent_comment is None and obj.replies_count > 0:
            # We limit to top 3 initial replies in the main list, the rest fetched via separate endpoint if needed
            replies = obj.replies.filter(is_deleted=False).select_related('user', 'user__profile')[:3]
            return BlogCommentReplySerializer(replies, many=True, context=self.context).data
        return []


class BlogCommentReplySerializer(serializers.ModelSerializer):
    """Simplified identical serializer to prevent circular dependency in get_replies."""
    user = AuthorBasicSerializer(read_only=True)
    reply_count = serializers.IntegerField(source='replies_count', read_only=True)
    
    class Meta:
        model = BlogComment
        fields = [
            'id', 'blog', 'user', 'parent_comment', 'comment_text',
            'media_file', 'reply_count', 'is_edited', 'created_at', 'updated_at'
        ]
