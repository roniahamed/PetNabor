from rest_framework.pagination import PageNumberPagination  
from rest_framework.response import Response


class NotificationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'unread_count': self.request.user.notifications.filter(is_read=False).count(),
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data
        })
    