from rest_framework.pagination import CursorPagination

class BlogCursorPagination(CursorPagination):
    """
    Cursor pagination for fast, consistent scrolling over lots of blogs.
    Sorted by created_at by default.
    """
    page_size = 10
    ordering = '-created_at'


class CommentCursorPagination(CursorPagination):
    """
    Cursor pagination for comments.
    Sorted by created_at.
    """
    page_size = 20
    ordering = '-created_at'
