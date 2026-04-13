from rest_framework.pagination import CursorPagination


class StandardCursorPagination(CursorPagination):
    page_size = 20
    ordering = '-created_at'
    max_page_size = 100 
    