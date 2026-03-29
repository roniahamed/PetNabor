from rest_framework import viewsets, status, generics, views, serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter, OpenApiTypes
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied
from django.db.models import Q

from .models import FriendRequest, Friendship, UserBlock
from .serializers import (
    FriendRequestSerializer, 
    FriendshipSerializer, 
    NearbyUserSerializer,
    UserBlockSerializer,
    UserActionSerializer,
    CreateFriendRequestSerializer,
    PublicUserSerializer,
    SuggestedUserSerializer
)
from django.contrib.auth import get_user_model
from . import services
from .paginations import FriendRequestPagination, FriendPagination, StandardResultsSetPagination
from .filters import UserFilter

class UnfriendView(views.APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=UserActionSerializer,
        responses={200: inline_serializer(
            name="UnfriendResponse",
            fields={"status": serializers.CharField()}
        )}
    )
    def post(self, request):
        serializer = UserActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        friend_id = serializer.validated_data['user_id']
            
        try:
            services.remove_friend(request.user, friend_id)
            return Response({'status': 'Friend removed successfully'})
        except NotFound as e:
            err_msg = str(e.detail[0]) if isinstance(e.detail, list) else str(e.detail)
            return Response({'error': err_msg}, status=status.HTTP_404_NOT_FOUND)


class FriendRequestViewSet(viewsets.ModelViewSet):
    serializer_class = FriendRequestSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = FriendRequestPagination

    def get_queryset(self):
        user = self.request.user
        queryset = FriendRequest.objects.select_related(
            'sender__profile', 
            'receiver__profile'
        ).filter(Q(sender=user) | Q(receiver=user)).order_by('-created_at')
        
        # Security: Filter out blocked users from showing up in pending requests
        blocked_ids = list(UserBlock.objects.filter(blocker=user).values_list('blocked_user_id', flat=True))
        blocked_by_ids = list(UserBlock.objects.filter(blocked_user=user).values_list('blocker_id', flat=True))
        exclude_ids = set(blocked_ids + blocked_by_ids)
        
        if exclude_ids:
            queryset = queryset.exclude(
                Q(sender=user, receiver_id__in=exclude_ids) | Q(receiver=user, sender_id__in=exclude_ids)
            )
        
        req_type = self.request.query_params.get('type')
        if req_type == 'sent':
            queryset = queryset.filter(sender=user)
        elif req_type == 'received':
            queryset = queryset.filter(receiver=user)
            
        return queryset

    def create(self, request, *args, **kwargs):
        payload_serializer = CreateFriendRequestSerializer(data=request.data)
        payload_serializer.is_valid(raise_exception=True)
        receiver_id = payload_serializer.validated_data['receiver_id']
        
        try:
            freq, auto_accepted = services.send_friend_request(request.user, receiver_id)
            if auto_accepted:
                return Response({'message': 'Friend request accepted automatically'}, status=status.HTTP_201_CREATED)
            
            res_serializer = self.get_serializer(freq)
            return Response(res_serializer.data, status=status.HTTP_201_CREATED)
        except (ValidationError, NotFound) as e:
            err_msg = str(e.detail[0]) if isinstance(e.detail, list) else str(e.detail)
            return Response({'error': err_msg}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        try:
            friend_request = self.get_object()
            services.accept_friend_request(request.user, friend_request)
            return Response({'status': 'Friend request accepted'})
        except (ValidationError, PermissionDenied) as e:
            err_msg = str(e.detail[0]) if isinstance(e.detail, list) else str(e.detail)
            return Response({'error': err_msg}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        try:
            friend_request = self.get_object()
            services.reject_friend_request(request.user, friend_request)
            return Response({'status': 'Friend request rejected'})
        except (ValidationError, PermissionDenied) as e:
            err_msg = str(e.detail[0]) if isinstance(e.detail, list) else str(e.detail)
            return Response({'error': err_msg}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        try:
            friend_request = self.get_object()
            services.cancel_friend_request(request.user, friend_request)
            return Response({'status': 'Friend request cancelled'})
        except (ValidationError, PermissionDenied) as e:
            err_msg = str(e.detail[0]) if isinstance(e.detail, list) else str(e.detail)
            return Response({'error': err_msg}, status=status.HTTP_400_BAD_REQUEST)


class BlockUserView(views.APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses=UserBlockSerializer(many=True),
    )
    def get(self, request):
        blocks = UserBlock.objects.filter(blocker=request.user).order_by('-created_at')
        
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(blocks, request)
        if page is not None:
            serializer = UserBlockSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)

        serializer = UserBlockSerializer(blocks, many=True, context={'request': request})
        return Response(serializer.data)

    @extend_schema(
        request=UserActionSerializer,
        responses={200: inline_serializer(
            name="BlockUserResponse",
            fields={"status": serializers.CharField()}
        )}
    )
    def post(self, request):
        serializer = UserActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        blocked_user_id = serializer.validated_data['user_id']
            
        try:
            services.block_user(request.user, blocked_user_id)
            return Response({'status': 'User blocked successfully'})
        except NotFound as e:
            err_msg = str(e.detail[0]) if isinstance(e.detail, list) else str(e.detail)
            return Response({'error': err_msg}, status=status.HTTP_404_NOT_FOUND)

    @extend_schema(
        request=UserActionSerializer,
        responses={200: inline_serializer(
            name="UnblockUserResponse",
            fields={"status": serializers.CharField()}
        )}
    )
    def delete(self, request):
        serializer = UserActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        blocked_user_id = serializer.validated_data['user_id']
            
        try:
            services.unblock_user(request.user, blocked_user_id)
            return Response({'status': 'User unblocked successfully'})
        except NotFound as e:
             err_msg = str(e.detail[0]) if isinstance(e.detail, list) else str(e.detail)
             return Response({'error': err_msg}, status=status.HTTP_404_NOT_FOUND)


class FriendListView(generics.ListAPIView):
    serializer_class = FriendshipSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = FriendPagination

    def get_queryset(self):
        user = self.request.user
        queryset = (
            Friendship.objects.select_related("sender__profile", "receiver__profile")
            .filter(Q(sender=user) | Q(receiver=user))
            .order_by("-created_at")
        )

        # Security: Filter out blocked users from showing up in the list
        blocked_ids = list(
            UserBlock.objects.filter(blocker=user).values_list("blocked_user_id", flat=True)
        )
        blocked_by_ids = list(
            UserBlock.objects.filter(blocked_user=user).values_list("blocker_id", flat=True)
        )
        exclude_ids = set(blocked_ids + blocked_by_ids)

        if exclude_ids:
            # Exclude memberships where the other user is in exclude_ids
            queryset = queryset.exclude(
                Q(sender=user, receiver_id__in=exclude_ids)
                | Q(receiver=user, sender_id__in=exclude_ids)
            )

        friend_type = self.request.query_params.get("type")  # 'petpals' or 'petnabors'
        if friend_type:
            # We filter based on the type of the friend (the other user)
            if friend_type == "petpals":
                queryset = queryset.filter(
                    Q(sender=user, receiver__user_type="patpal")
                    | Q(receiver=user, sender__user_type="patpal")
                )
            elif friend_type == "petnabors":
                queryset = queryset.filter(
                    Q(sender=user, receiver__user_type="patnabor")
                    | Q(receiver=user, sender__user_type="patnabor")
                )

        return queryset


class UserSearchView(views.APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter("q", OpenApiTypes.STR, description="Search query"),
            OpenApiParameter("type", OpenApiTypes.STR, description="User type (e.g. patpal, patnabor)"),
            OpenApiParameter("radius", OpenApiTypes.INT, description="Search radius in miles"),
            OpenApiParameter("include_friends", OpenApiTypes.BOOL, description="Include existing friends"),
            OpenApiParameter("city", OpenApiTypes.STR, description="City name"),
            OpenApiParameter("state", OpenApiTypes.STR, description="State code"),
        ],
        responses=NearbyUserSerializer(many=True),
    )
    def get(self, request):
        user_filter = UserFilter(request)
        
        user_type = user_filter.get_user_type()
        radius = user_filter.get_radius()
        search_query = user_filter.get_search_query()
        include_friends = user_filter.get_include_friends()
        city = user_filter.get_city()
        state = user_filter.get_state()
        
        results = services.get_nearby_users(
            request.user, 
            user_type=user_type, 
            radius=radius, 
            search_query=search_query,
            include_friends=include_friends,
            city=city,
            state=state
        )
        
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(results, request)
        if page is not None:
            serializer = NearbyUserSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)

        serializer = NearbyUserSerializer(results, many=True, context={'request': request})
        return Response(serializer.data)


class PublicUserDetailsView(views.APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses=PublicUserSerializer,
    )
    def get(self, request, user_id):
        try:
            target_user = get_user_model().objects.select_related('profile').get(id=user_id, is_active=True)
        except (get_user_model().DoesNotExist, ValidationError):
            raise NotFound("User not found")

        if services.is_blocked(request.user, target_user):
            raise NotFound("User not found")

        serializer = PublicUserSerializer(target_user, context={'request': request})
        return Response(serializer.data)


class SuggestedFriendsView(views.APIView):
    """
    API view to retrieve suggested friends for the current user.
    Suggestions are calculated considering mutual friends and distance.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses=SuggestedUserSerializer(many=True),
        tags=["friends"]
    )
    def get(self, request):
        limit = request.query_params.get("limit", 20)
        try:
            limit = int(limit)
        except ValueError:
            limit = 20

        # Retrieve the un-evaluated QuerySet from the service
        suggestions_queryset = services.get_suggested_friends(request.user, limit=limit)
        
        paginator = StandardResultsSetPagination()
        # Ensure we can optionally override page size dynamically for 'limit' param if StandardResultsSetPagination supports it
        paginator.page_size = limit
        
        page = paginator.paginate_queryset(suggestions_queryset, request)
        if page is not None:
            serializer = SuggestedUserSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)

        # Fallback if pagination fails or is disabled
        serializer = SuggestedUserSerializer(suggestions_queryset[:limit], many=True, context={'request': request})
        return Response(serializer.data)
