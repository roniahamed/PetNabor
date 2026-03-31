"""
Views for managing friendships, friend requests, user blocks, and friend suggestions.
"""
from rest_framework import viewsets, status, generics, views, serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    inline_serializer,
    OpenApiParameter,
    OpenApiTypes,
)
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
    SuggestedUserSerializer,
    MapNearbyUserSerializer,
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


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                name="type",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter request direction.",
                required=False,
                enum=["sent", "received"],
            ),
            OpenApiParameter(
                name="page",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Page number for paginated results.",
                required=False,
                default=1,
            ),
            OpenApiParameter(
                name="page_size",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Number of requests per page.",
                required=False,
                default=20,
            ),
        ]
    )
)
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
        parameters=[
            OpenApiParameter(
                name="page",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Page number for blocked users.",
                required=False,
                default=1,
            ),
            OpenApiParameter(
                name="page_size",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Number of blocked users per page.",
                required=False,
                default=20,
            ),
        ],
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


@extend_schema_view(
    get=extend_schema(
        parameters=[
            OpenApiParameter(
                name="type",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter friends by user group.",
                required=False,
                enum=["petpals", "petnabors"],
            ),
            OpenApiParameter(
                name="page",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Page number for paginated results.",
                required=False,
                default=1,
            ),
            OpenApiParameter(
                name="page_size",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Number of friends per page.",
                required=False,
                default=20,
            ),
        ]
    )
)
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
            OpenApiParameter(
                name="q",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Search keyword for nearby users.",
                required=False,
            ),
            OpenApiParameter(
                name="type",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="User type filter.",
                required=False,
                enum=["patpal", "patnabor"],
            ),
            OpenApiParameter(
                name="radius",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Distance radius in miles.",
                required=False,
                default=25,
            ),
            OpenApiParameter(
                name="include_friends",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="Include already-friended users.",
                required=False,
                default=False,
            ),
            OpenApiParameter(
                name="city",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="City-based filter.",
                required=False,
            ),
            OpenApiParameter(
                name="state",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="State or region filter.",
                required=False,
            ),
            OpenApiParameter(
                name="page",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Page number for paginated results.",
                required=False,
                default=1,
            ),
            OpenApiParameter(
                name="page_size",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Number of results per page.",
                required=False,
                default=20,
            ),
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
        parameters=[
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Maximum suggestions to return.",
                required=False,
                default=20,
            ),
            OpenApiParameter(
                name="page",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Page number for paginated results.",
                required=False,
                default=1,
            ),
            OpenApiParameter(
                name="page_size",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Number of suggestions per page.",
                required=False,
                default=20,
            ),
        ],
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


class MapNearbyUsersView(views.APIView):
    """
    Dual-mode Map Search API.

    ── MODE 1: Circle Search (lat + lng + radius) ───────────────────────────
    Client drops a pin on the map.
    Returns paginated users within `radius` miles, ordered nearest-first.
    Use this for the "list view" panel next to the map.

    ── MODE 2: Viewport Search (bbox) ───────────────────────────────────────
    Client sends the 4 corners of the visible map area.
    Returns ALL users inside that rectangle (no pages — just a limit cap).
    Re-call this on every map pan/zoom with the new viewport bounds.
    Use this to render pins directly on the map.

    Both modes return each user's latitude & longitude so the frontend
    can place pins, and friendship_status so action buttons can be shown.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Find users near a map location (circle or viewport mode)",
        description=(
            "**Circle mode** (`lat` + `lng` + `radius`): paginated list of users "
            "within the radius. Good for a side-panel list.\n\n"
            "**Viewport mode** (`bbox`): pass `bbox=minLng,minLat,maxLng,maxLat` "
            "(the visible map bounds). Returns ALL users in the viewport up to "
            "`limit` (max 500). No pages — re-fetch on every pan/zoom."
        ),
        parameters=[
            # ── Circle mode params ──────────────────────────────────────────
            OpenApiParameter(
                name="lat",
                type=OpenApiTypes.FLOAT,
                location=OpenApiParameter.QUERY,
                description="[Circle mode] Latitude of the dropped pin (WGS-84).",
                required=False,
            ),
            OpenApiParameter(
                name="lng",
                type=OpenApiTypes.FLOAT,
                location=OpenApiParameter.QUERY,
                description="[Circle mode] Longitude of the dropped pin (WGS-84).",
                required=False,
            ),
            OpenApiParameter(
                name="radius",
                type=OpenApiTypes.FLOAT,
                location=OpenApiParameter.QUERY,
                description="[Circle mode] Radius in miles. Default 25.",
                required=False,
                default=25,
            ),
            OpenApiParameter(
                name="page",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="[Circle mode] Page number for paginated results.",
                required=False,
                default=1,
            ),
            OpenApiParameter(
                name="page_size",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="[Circle mode] Results per page (max 100).",
                required=False,
                default=20,
            ),
            # ── Viewport mode params ────────────────────────────────────────
            OpenApiParameter(
                name="bbox",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description=(
                    "[Viewport mode] Visible map bounds as `minLng,minLat,maxLng,maxLat`. "
                    "Example: `bbox=90.35,23.75,90.47,23.87`. "
                    "When present, lat/lng/radius are ignored."
                ),
                required=False,
            ),
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="[Viewport mode] Max pins to return (default 300, max 500).",
                required=False,
                default=300,
            ),
            # ── Shared params ───────────────────────────────────────────────
            OpenApiParameter(
                name="type",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by user type.",
                required=False,
                enum=["patpal", "patnabor"],
            ),
            OpenApiParameter(
                name="search",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Text search on first name, last name, or username.",
                required=False,
            ),
            OpenApiParameter(
                name="include_friends",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="Include already-friended users. Default true.",
                required=False,
                default=True,
            ),
        ],
        responses=MapNearbyUserSerializer(many=True),
        tags=["friends"],
    )
    def get(self, request):
        # ── Shared optional filters ───────────────────────────────────────────
        raw_type        = request.query_params.get("type", "")
        user_type       = raw_type if raw_type in ("patpal", "patnabor") else None
        search_query    = request.query_params.get("search", "").strip()
        include_friends = request.query_params.get("include_friends", "true").lower() == "true"

        # ════════════════════════════════════════════════════════════════════
        # MODE 2 — Viewport / BBox  (triggered when `bbox` param is present)
        # ════════════════════════════════════════════════════════════════════
        bbox_raw = request.query_params.get("bbox", "").strip()
        if bbox_raw:
            try:
                min_lng, min_lat, max_lng, max_lat = [float(v) for v in bbox_raw.split(",")]
            except (ValueError, TypeError):
                return Response(
                    {"error": "`bbox` must be `minLng,minLat,maxLng,maxLat` — e.g. `90.35,23.75,90.47,23.87`."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validate bounds
            if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
                return Response({"error": "Latitude values must be between -90 and 90."}, status=status.HTTP_400_BAD_REQUEST)
            if not (-180 <= min_lng <= 180 and -180 <= max_lng <= 180):
                return Response({"error": "Longitude values must be between -180 and 180."}, status=status.HTTP_400_BAD_REQUEST)
            if min_lat >= max_lat or min_lng >= max_lng:
                return Response({"error": "`min_lat` < `max_lat` and `min_lng` < `max_lng` required."}, status=status.HTTP_400_BAD_REQUEST)

            try:
                limit = min(int(request.query_params.get("limit", 300)), 500)
            except (ValueError, TypeError):
                limit = 300

            # No pagination — return all pins in viewport up to limit
            results = services.get_users_in_bbox(
                current_user=request.user,
                min_lat=min_lat,
                max_lat=max_lat,
                min_lng=min_lng,
                max_lng=max_lng,
                user_type=user_type,
                search_query=search_query,
                include_friends=include_friends,
                limit=limit,
            )
            serializer = MapNearbyUserSerializer(results, many=True, context={"request": request})
            return Response({
                "mode": "viewport",
                "count": len(serializer.data),
                "results": serializer.data,
            })

        # ════════════════════════════════════════════════════════════════════
        # MODE 1 — Circle Search  (lat + lng + radius, paginated)
        # ════════════════════════════════════════════════════════════════════
        try:
            latitude  = float(request.query_params["lat"])
            longitude = float(request.query_params["lng"])
        except (KeyError, ValueError, TypeError):
            return Response(
                {"error": "Provide either `bbox` (viewport mode) or `lat`+`lng` (circle mode)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
            return Response(
                {"error": "`lat` must be -90..90 and `lng` must be -180..180."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            radius = float(request.query_params.get("radius", 25))
            if radius <= 0:
                radius = 25.0
        except (ValueError, TypeError):
            radius = 25.0

        queryset = services.get_users_near_map_point(
            current_user=request.user,
            latitude=latitude,
            longitude=longitude,
            radius=radius,
            user_type=user_type,
            search_query=search_query,
            include_friends=include_friends,
        )

        paginator = StandardResultsSetPagination()
        page      = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = MapNearbyUserSerializer(page, many=True, context={"request": request})
            return paginator.get_paginated_response(serializer.data)

        serializer = MapNearbyUserSerializer(queryset, many=True, context={"request": request})
        return Response(serializer.data)

