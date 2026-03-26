from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import Meeting, MeetingFeedback
from .serializers import MeetingSerializer, MeetingFeedbackSerializer
from .paginations import MeetingPagination
from api.friends.models import Friendship

User = get_user_model()

class MeetingViewSet(viewsets.ModelViewSet):
    serializer_class = MeetingSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = MeetingPagination

    def get_queryset(self):
        user = self.request.user
        return Meeting.objects.filter(Q(sender=user) | Q(receiver=user))

    def perform_create(self, serializer):
        sender = self.request.user
        receiver = serializer.validated_data.get('receiver')

        if sender == receiver:
            raise ValidationError({"detail": "You cannot request a meeting with yourself."})

        # Check if users are friends
        is_friend = Friendship.objects.filter(
            Q(sender=sender, receiver=receiver) | Q(sender=receiver, receiver=sender)
        ).exists()

        if not is_friend:
            raise PermissionDenied("You can only request meetings with friends.")

        serializer.save(sender=sender)

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        today = timezone.localdate()
        meetings = self.get_queryset().filter(
            visit_date__gte=today,
            status__in=['PENDING', 'ACCEPTED']
        )
        page = self.paginate_queryset(meetings)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(meetings, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def previous(self, request):
        today = timezone.localdate()
        meetings = self.get_queryset().filter(
            Q(visit_date__lt=today) | Q(status__in=['CANCELLED', 'COMPLETED'])
        ).distinct()
        page = self.paginate_queryset(meetings)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(meetings, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        meeting = self.get_object()
        
        if meeting.receiver != request.user:
            raise PermissionDenied("Only the receiver can accept the meeting request.")
            
        if meeting.status != 'PENDING':
            raise ValidationError({"detail": "Only pending meetings can be accepted."})

        meeting.status = 'ACCEPTED'
        meeting.save()
        return Response({'status': 'Meeting accepted'})

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        meeting = self.get_object()
        
        if meeting.status in ['CANCELLED', 'COMPLETED']:
            raise ValidationError({"detail": "Meeting cannot be cancelled from its current status."})

        meeting.status = 'CANCELLED'
        meeting.save()
        return Response({'status': 'Meeting cancelled'})

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        meeting = self.get_object()
        
        if meeting.status != 'ACCEPTED':
            raise ValidationError({"detail": "Only accepted meetings can be completed."})
            
        meeting.status = 'COMPLETED'
        meeting.save()
        return Response({'status': 'Meeting completed'})


class MeetingFeedbackViewSet(viewsets.ModelViewSet):
    serializer_class = MeetingFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = MeetingPagination

    def get_queryset(self):
        user = self.request.user
        return MeetingFeedback.objects.filter(Q(reviewer=user) | Q(reviewee=user))

    def perform_create(self, serializer):
        reviewer = self.request.user
        meeting = serializer.validated_data.get('meeting')
        reviewee = serializer.validated_data.get('reviewee')

        # Provide a more specific check that meeting is actually COMPLETED
        if meeting.status != 'COMPLETED':
            raise ValidationError({"detail": "Feedback can only be given for completed meetings."})

        if reviewer not in [meeting.sender, meeting.receiver]:
            raise PermissionDenied("You cannot give feedback for a meeting you are not part of.")

        if reviewee not in [meeting.sender, meeting.receiver]:
            raise ValidationError({"detail": "Reviewee must be a participant of the meeting."})

        if reviewer == reviewee:
            raise ValidationError({"detail": "You cannot leave feedback for yourself."})
            
        # Check if feedback already exists
        if MeetingFeedback.objects.filter(meeting=meeting, reviewer=reviewer).exists():
            raise ValidationError({"detail": "You have already provided feedback for this meeting."})

        serializer.save(reviewer=reviewer)

    @action(detail=False, methods=['get'], url_path='user/(?P<user_id>[^/.]+)')
    def user_feedbacks(self, request, user_id=None):
        """
        GET /api/meetings/feedback/user/{user_id}/
        Returns all public feedbacks where the given user is the reviewee.
        Accessible by any authenticated user (e.g. viewing a profile).
        """
        try:
            target_user = User.objects.get(id=user_id)
        except (User.DoesNotExist, ValueError):
            raise NotFound("User not found.")

        feedbacks = MeetingFeedback.objects.filter(
            reviewee=target_user,
            is_public=True
        ).select_related('reviewer', 'meeting')

        page = self.paginate_queryset(feedbacks)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(feedbacks, many=True)
        return Response(serializer.data)
