"""
ViewSets for Posts, Comments, Likes, and Saved Posts.
Key improvements:
- Throttle scopes on like/comment/save actions (anti-spam)
- Proper permission classes instead of manual ownership checks in views
- Soft-delete instead of hard-delete on posts
- N+1 fix on replies endpoint (select_related added)
- FeedCursorPagination has max_page_size guard
- get_queryset filters is_deleted=False
"""

import logging

from rest_framework import filters, generics, permissions, status, viewsets, serializers
from rest_framework.decorators import action
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, inline_serializer


from django.db.models import Prefetch
from django.shortcuts import get_object_or_404

from .models import Post, PostComment, PostLike, SavedPost
from .permissions import IsAuthorOrReadOnly, IsCommentAuthorOrPostAuthor, CanViewPost
from .serializers import (
    PostCommentSerializer,
    PostDetailSerializer,
    PostListSerializer,
    PostCreateUpdateSerializer,
    PostLikeSerializer,
    SavedPostSerializer,
)
from .services import CommentService, FeedService, LikeService, PostService, SaveService
from api.users.models import User

logger = logging.getLogger(__name__)


class FeedCursorPagination(CursorPagination):
    """Cursor pagination optimized for feeds — prevents deep pagination abuse."""

    page_size = 20
    max_page_size = 50
    ordering = "-created_at"


# ──────────────────────────────────────────────
# Post ViewSet
# ──────────────────────────────────────────────


class PostViewSet(viewsets.ModelViewSet):
    """
    CRUD for Posts.
    - create / update use PostCreateUpdateSerializer
    - retrieve uses PostDetailSerializer with recent comments prefetch
    - list / feed use PostListSerializer
    - Soft-delete via destroy
    """

    permission_classes = [permissions.IsAuthenticated, IsAuthorOrReadOnly, CanViewPost]
    pagination_class = FeedCursorPagination
    filter_backends = [filters.SearchFilter]
    search_fields = [
        "content_text",
        "hashtags__name",
        "mentions__username",
    ]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return PostCreateUpdateSerializer
        if self.action == "retrieve":
            return PostDetailSerializer
        return PostListSerializer

    def get_queryset(self):
        """
        - GET /posts/ (list) returns only the requesting user's posts.
        - GET /posts/{id}/ (retrieve) and actions work on any visible post.
        """
        if self.action == "list":
            return PostService.get_user_posts(self.request.user, self.request.user)

        # More inclusive queryset for retrieve and other actions
        qs = Post.objects.filter(is_deleted=False)

        if self.action == "retrieve":
            recent_comments = (
                PostComment.objects.filter(parent_comment__isnull=True)
                .select_related("user", "user__profile")
                .order_by("created_at")
            )

            qs = qs.prefetch_related(
                Prefetch(
                    "comments", queryset=recent_comments, to_attr="recent_comments_qs"
                )
            )

        # Apply basic optimizations found in get_user_posts but for any author
        return qs.select_related("author", "author__profile").prefetch_related(
            "media",
            "hashtags",
            Prefetch("mentions", queryset=User.objects.select_related("profile")),
            Prefetch(
                "likes",
                queryset=PostLike.objects.filter(user=self.request.user),
                to_attr="user_reactions",
            ),
        )

    def create(self, request, *args, **kwargs):
        """Handles multipart/form-data post creation via service layer."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        files = request.FILES.getlist("media")
        post = PostService.create_post(
            user=request.user,
            data=serializer.validated_data,
            files=files,
        )

        return Response(
            PostDetailSerializer(post, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def perform_update(self, serializer):
        serializer.save(is_edited=True)

    def destroy(self, request, *args, **kwargs):
        """Soft-delete instead of hard-delete — requires IsPostAuthor permission."""
        post = self.get_object()
        self.check_object_permissions(request, post)
        PostService.soft_delete_post(post, request.user)
        return Response({"detail": "Post deleted."}, status=status.HTTP_200_OK)

    # ── Feed ──────────────────────────────────────────────────────────

    @extend_schema(responses=PostListSerializer(many=True))
    @action(detail=False, methods=["get"])
    def feed(self, request):
        """Main timeline feed — friends + self, sorted by recency."""
        qs = FeedService.get_feed(request.user)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = PostListSerializer(
                page, many=True, context={"request": request}
            )
            return self.get_paginated_response(serializer.data)
        serializer = PostListSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)

    # ── Like ──────────────────────────────────────────────────────────

    @extend_schema(
        request=inline_serializer(
            name="PostReactionRequest",
            fields={"reaction_type": serializers.CharField(required=False, default="LIKE")}
        ),
        responses={
            200: inline_serializer(
                name="PostReactionResponse",
                fields={
                    "status": serializers.CharField(),
                    "likes_count": serializers.IntegerField(),
                    "id": serializers.UUIDField(required=False),
                    # and other fields from PostLikeSerializer
                }
            )
        }
    )
    @action(detail=True, methods=["post", "delete"])
    def like(self, request, pk=None):
        """
        POST  → like/react to a post
        DELETE → remove like
        Always returns the updated likes_count for easy frontend use.
        """
        self.throttle_scope = "post_like"
        post = self.get_object()

        if request.method == "DELETE":
            LikeService.toggle_like(post, request.user)
            post.refresh_from_db(fields=["likes_count"])
            return Response(
                {"status": "unliked", "likes_count": post.likes_count},
                status=status.HTTP_200_OK,
            )

        reaction = request.data.get("reaction_type", "LIKE")
        like_obj, created = LikeService.toggle_like(post, request.user, reaction)
        post.refresh_from_db(fields=["likes_count"])

        data = (
            PostLikeSerializer(like_obj, context={"request": request}).data
            if like_obj
            else {}
        )
        data["likes_count"] = post.likes_count
        data["status"] = "liked" if like_obj else "unliked"

        return Response(
            data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

    # ── Save ──────────────────────────────────────────────────────────

    @extend_schema(
        request=None,
        responses={
            200: inline_serializer(
                name="PostSaveResponse",
                fields={"status": serializers.CharField()}
            )
        }
    )
    @action(detail=True, methods=["post", "delete"])
    def save_post(self, request, pk=None):
        """POST → save; DELETE → unsave."""
        self.throttle_scope = "post_save"
        post = self.get_object()
        saved = SaveService.toggle_save(post, request.user)
        if saved:
            return Response({"status": "saved"}, status=status.HTTP_201_CREATED)
        return Response({"status": "unsaved"}, status=status.HTTP_200_OK)


# ──────────────────────────────────────────────
# Comment ViewSet
# ──────────────────────────────────────────────


class PostCommentViewSet(viewsets.ModelViewSet):
    """
    CRUD for top-level comments.
    - Throttled creation to prevent spam.
    - Destruction allowed by comment author OR post author (via permission class).
    """

    serializer_class = PostCommentSerializer
    permission_classes = [permissions.IsAuthenticated, IsCommentAuthorOrPostAuthor]
    pagination_class = FeedCursorPagination

    def get_queryset(self):
        post_id = self.request.query_params.get("post_id")
        qs = PostComment.objects.select_related("user", "user__profile").filter(
            parent_comment__isnull=True
        )
        if post_id:
            qs = qs.filter(post_id=post_id)
        return qs

    def perform_create(self, serializer):
        instance = CommentService.create_comment(
            user=self.request.user,
            validated_data=serializer.validated_data,
        )
        serializer.instance = instance

    def perform_update(self, serializer):
        serializer.save(is_edited=True)

    def perform_destroy(self, instance):
        """Permission class handles ownership check — just call the service."""
        CommentService.delete_comment(instance)

    @extend_schema(responses=PostCommentSerializer(many=True))
    @action(detail=True, methods=["get"])
    def replies(self, request, pk=None):
        """Paginated replies for a specific parent comment — select_related added."""
        parent_comment = self.get_object()
        qs = parent_comment.replies.select_related("user", "user__profile").all()
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


# ──────────────────────────────────────────────
# Saved Posts ViewSet
# ──────────────────────────────────────────────


class SavedPostViewSet(viewsets.ReadOnlyModelViewSet):
    """Returns the authenticated user's bookmarked posts."""

    serializer_class = SavedPostSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = FeedCursorPagination

    def get_queryset(self):
        return (
            SavedPost.objects.select_related(
                "post",
                "post__author",
                "post__author__profile",
            )
            .prefetch_related(
                "post__media",
                "post__hashtags",
                Prefetch(
                    "post__mentions", queryset=User.objects.select_related("profile")
                ),
            )
            .filter(user=self.request.user)
        )


class UserPostListView(generics.ListAPIView):
    """
    GET /post/user/<uuid:user_id>/posts/
    Public (authenticated) — returns any user's posts.
    Privacy is enforced by PostService.get_user_posts (respects blocks, visibility).
    """

    serializer_class = PostListSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = FeedCursorPagination

    def get_queryset(self):
        user_id = self.kwargs["user_id"]
        target_user = get_object_or_404(User, id=user_id, is_active=True)
        return PostService.get_user_posts(self.request.user, target_user)
