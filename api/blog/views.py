import logging
from django.db.models import F
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.core.cache import cache
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from .models import Blog, BlogComment
from .serializers import (
    BlogListSerializer,
    BlogDetailSerializer,
    BlogCommentSerializer,
)
from .services import BlogService
from .pagination import BlogCursorPagination, CommentCursorPagination

logger = logging.getLogger(__name__)


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')


class BlogViewSet(viewsets.ModelViewSet):
    """
    CRUD for Blogs.
    Uses Cursor Pagination, Full Text Search, and robust Pre-fetching.
    """
    queryset = Blog.objects.filter(is_deleted=False).select_related('author', 'author__profile', 'category')
    lookup_field = 'slug'
    pagination_class = BlogCursorPagination
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'views_count', 'likes_count']

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'comments']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        if self.action in ['list', 'search', 'popular']:
            return BlogListSerializer
        return BlogDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        
        # Only authors see unpublished
        if self.action == 'list':
            qs = qs.filter(is_published=True)

        user = self.request.user
        if user.is_authenticated and self.action != 'list':
            # Add an annotation for 'is_liked' to prevent N+1 dynamically if possible,
            # For simplicity, we fallback to our serializer method field or just a prefetch
            pass

        # PostgreSQL Full-Text Search
        search_term = self.request.query_params.get('search', None)
        if search_term:
            search_query = SearchQuery(search_term)
            search_vector = SearchVector('title', weight='A') + SearchVector('content_body', weight='B') + SearchVector('tags', weight='C')
            qs = qs.annotate(
                search=search_vector,
                rank=SearchRank(search_vector, search_query)
            ).filter(search=search_query).order_class('-rank', '-created_at')

        # Generic Filters
        category = self.request.query_params.get('category', None)
        if category:
            qs = qs.filter(category__slug=category)
            
        author_id = self.request.query_params.get('author_id', None)
        if author_id:
            qs = qs.filter(author_id=author_id)

        return qs

    def list(self, request, *args, **kwargs):
        """
        List all published blogs. Uses Redis caching for performance.
        Skip caching if there are active search/filter query params.
        """
        if request.query_params:
            return super().list(request, *args, **kwargs)

        cache_key = "blog_list_cache"
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)

        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, 60 * 5)  # 5 minutes
        return response

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def popular(self, request):
        """
        Retrieves top trending/popular posts based on views and likes.
        Cached separately for fast access.
        """
        cache_key = "blog_popular_cache"
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)

        qs = self.get_queryset().filter(is_published=True).annotate(
            trend_score=(F('views_count') * 0.4 + F('likes_count') * 0.6)
        ).order_by('-trend_score')[:10]
        
        # Use BlogListSerializer instead of Detail
        serializer = BlogListSerializer(qs, many=True, context={'request': request})
        
        # Flat structure as requested
        result_data = {
            "next": None,
            "previous": None,
            "results": serializer.data
        }
        cache.set(cache_key, result_data, 60 * 15)
        return Response(result_data)

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve blog details and track views asyncly.
        """
        instance = self.get_object()
        
        # Track View Async via Celery
        ip_addr = get_client_ip(request)
        user_id = request.user.id if request.user.is_authenticated else None
        
        # We import here or at the top
        from .tasks import track_view_async
        track_view_async.delay(instance.id, ip_addr, user_id)
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


    def perform_create(self, serializer):
        instance = serializer.save(author=self.request.user)
        # Clear main list cache
        cache.delete("blog_list_cache")
        # Trigger WebP processing if cover exists
        if instance.cover_image:
            from .tasks import process_blog_cover_task
            process_blog_cover_task.delay(str(instance.id))

    def perform_update(self, serializer):
        # ensure only owner can update
        if self.get_object().author != self.request.user:
            raise permissions.PermissionDenied("You do not own this blog.")
        instance = serializer.save()
        cache.delete("blog_list_cache")
        
        if 'cover_image' in self.request.FILES:
            from .tasks import process_blog_cover_task
            process_blog_cover_task.delay(str(instance.id))

    def perform_destroy(self, instance):
        if instance.author != self.request.user:
            raise permissions.PermissionDenied("You do not own this blog.")
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted'])
        cache.delete("blog_list_cache")

    # ──────────────────────────────────────────────
    # Action Endpoints
    # ──────────────────────────────────────────────

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated], throttle_classes=[ScopedRateThrottle])
    def like(self, request, slug=None):
        """Toggle like for this blog."""
        blog = self.get_object()
        self.throttle_scope = 'post_like' # Assuming throttler named post_like or similar exists
        
        is_liked = BlogService.toggle_like(blog=blog, user=request.user)
        # Refresh from db to get fresh count
        blog.refresh_from_db(fields=['likes_count'])
        return Response({
            "is_liked": is_liked,
            "likes_count": blog.likes_count
        })

    @action(detail=True, methods=['get', 'post'], permission_classes=[permissions.IsAuthenticatedOrReadOnly])
    def comments(self, request, slug=None):
        """
        GET: List top-level comments for the blog with cursor pagination.
        POST: Create a comment/reply.
        """
        blog = self.get_object()

        if request.method == 'GET':
            # Fetch only top level comments, nested are handled inside the serializer up to a limit
            comments = BlogComment.objects.filter(
                blog=blog,
                parent_comment__isnull=True,
                is_deleted=False
            ).select_related('user', 'user__profile')
            
            paginator = CommentCursorPagination()
            page = paginator.paginate_queryset(comments, request)
            
            serializer = BlogCommentSerializer(page if page is not None else comments, many=True, context={'request': request})
            
            # Always use paginator's response method for consistent structure
            return paginator.get_paginated_response(serializer.data)

        if request.method == 'POST':
            text = request.data.get('comment_text')
            if not text:
                return Response({"detail": "comment_text is required"}, status=status.HTTP_400_BAD_REQUEST)
                
            parent_id = request.data.get('parent_id')
            media = request.FILES.get('media_file')

            try:
                comment = BlogService.create_comment(
                    blog=blog,
                    user=request.user,
                    text=text,
                    parent_id=parent_id,
                    media=media
                )
                blog.refresh_from_db(fields=['comments_count'])
                serializer = BlogCommentSerializer(comment, context={'request': request})
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except ValueError as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[permissions.AllowAny])
    def share(self, request, slug=None):
        """Increments share count. Just a simple metric tracker."""
        blog = self.get_object()
        Blog.objects.filter(id=blog.id).update(shares_count=F('shares_count') + 1)
        return Response({"detail": "Shared successfully."})


class BlogCommentViewSet(viewsets.ViewSet):
    """
    Allows operations strictly on comments globally (e.g. deletion, editing).
    """
    permission_classes = [permissions.IsAuthenticated]

    def destroy(self, request, pk=None):
        """Soft delete a comment."""
        success = BlogService.soft_delete_comment(comment_id=pk, user=request.user)
        if success:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({"detail": "Comment not found or access denied."}, status=status.HTTP_404_NOT_FOUND)

    def partial_update(self, request, pk=None):
        """Edit comment text."""
        try:
            comment = BlogComment.objects.get(id=pk, user=request.user, is_deleted=False)
            text = request.data.get('comment_text')
            if not text:
                return Response({"detail": "comment_text is required"}, status=status.HTTP_400_BAD_REQUEST)
                
            comment.comment_text = text
            comment.is_edited = True
            comment.save()
            return Response(BlogCommentSerializer(comment, context={'request': request}).data)
        except BlogComment.DoesNotExist:
             return Response({"detail": "Comment not found or access denied."}, status=status.HTTP_404_NOT_FOUND)
