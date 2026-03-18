"""
ViewSets for the Report app.
Improvements:
- Reports are immutable once submitted (no PUT/PATCH/DELETE for reporters)
- Admin can see all reports with select_related to avoid N+1
- IsReporterOrAdmin permission enforced at object level
- select_related('reporter') on all querysets
"""

from rest_framework import viewsets, permissions, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Report
from .serializers import ReportSerializer
from api.post.permissions import IsReporterOrAdmin
from api.post.views import FeedCursorPagination


class ReportViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    Reports are write-once (submit-only). No update or deletion by reporters.
    Admin can list all reports and mark them resolved via the `resolve` action.
    """
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAuthenticated, IsReporterOrAdmin]
    pagination_class = FeedCursorPagination

    def get_queryset(self):
        qs = Report.objects.select_related('reporter', 'reporter__profile')
        if self.request.user.is_staff:
            return qs.all()
        return qs.filter(reporter=self.request.user)

    def perform_create(self, serializer):
        serializer.save(reporter=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def resolve(self, request, pk=None):
        """Admin-only action to mark a report as resolved."""
        report = self.get_object()
        if report.is_resolved:
            return Response(
                {"detail": "This report is already resolved."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        report.is_resolved = True
        report.save(update_fields=['is_resolved', 'updated_at'])
        return Response({"detail": "Report marked as resolved."}, status=status.HTTP_200_OK)
