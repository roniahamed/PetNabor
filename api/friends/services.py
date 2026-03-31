"""
Business logic for friendships, friend requests, and user blocks.
"""
from django.contrib.gis.geos import Point
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied
from .models import FriendRequest, Friendship, UserBlock
from api.notifications.services import send_notification
from api.notifications.models import NotificationTypes

User = get_user_model()


def _invalidate_message_permission(user_a_id, user_b_id):
    """Lazily import and invalidate the messaging permission cache for a user pair."""
    try:
        from api.messaging.services import invalidate_messaging_permission
        invalidate_messaging_permission(user_a_id, user_b_id)
    except Exception:
        pass  # messaging app may not be installed in all test environments


def is_blocked(user_a, user_b):
    """Helper method to determine if a block exists in either direction."""
    return UserBlock.objects.filter(
        Q(blocker=user_a, blocked_user=user_b) | Q(blocker=user_b, blocked_user=user_a)
    ).exists()


def send_friend_request(sender, receiver_id):
    if str(sender.id) == str(receiver_id):
        raise ValidationError("Cannot send friend request to yourself")

    try:
        receiver = User.objects.get(id=receiver_id)
    except User.DoesNotExist:
        raise NotFound("User not found")

    # Check if blocked
    if is_blocked(sender, receiver):
        raise ValidationError("Cannot send request")

    # Check if already friends
    if Friendship.objects.filter(
        Q(sender=sender, receiver=receiver) | Q(sender=receiver, receiver=sender)
    ).exists():
        raise ValidationError("Already friends")

    # Check if request already exists
    existing_req = FriendRequest.objects.filter(
        sender=sender, receiver=receiver, status="pending"
    ).first()
    if existing_req:
        raise ValidationError("Friend request already sent")

    # Reverse pending request exists?
    reverse_req = FriendRequest.objects.filter(
        sender=receiver, receiver=sender, status="pending"
    ).first()
    if reverse_req:
        # Automatically accept — create Friendship, then clean up the request
        Friendship.objects.create(sender=receiver, receiver=sender)

        # Notify the original sender (receiver of this new request) that it was accepted.
        # Use accepter_id so the frontend can deeplink to the accepter's profile.
        send_notification(
            user_id=receiver.id,
            title="Friend Request Accepted",
            body=f"{sender.username} accepted your friend request.",
            notification_type=NotificationTypes.FRIEND_ACCEPT,
            data={"accepter_id": str(sender.id)},
        )
        reverse_req.delete()
        return None, True  # True means automatically accepted

    freq = FriendRequest.objects.create(sender=sender, receiver=receiver, status="pending")

    # Notify the receiver about the new friend request (include IDs for frontend deeplink)
    send_notification(
        user_id=receiver.id,
        title="New Friend Request",
        body=f"{sender.username} sent you a friend request.",
        notification_type=NotificationTypes.FRIEND_REQUEST,
        data={"sender_id": str(sender.id), "request_id": str(freq.id)},
    )
    return freq, False


def accept_friend_request(user, friend_request):
    if friend_request.receiver != user:
        raise PermissionDenied("Not authorized")
    if friend_request.status != "pending":
        raise ValidationError("Request already processed")

    if is_blocked(user, friend_request.sender):
        raise ValidationError("Cannot accept request, user is blocked")

    sender_id = friend_request.sender_id

    Friendship.objects.get_or_create(
        sender=friend_request.sender, receiver=friend_request.receiver
    )

    # Clean up the accepted request — data lives in Friendship model now
    friend_request.delete()

    # Invalidate messaging permission cache for this new friendship
    _invalidate_message_permission(user.id, sender_id)

    # Notify the sender that the request was accepted.
    # Use accepter_id so the frontend can deeplink to the accepter's profile.
    send_notification(
        user_id=sender_id,
        title="Friend Request Accepted",
        body=f"{user.username} accepted your friend request.",
        notification_type=NotificationTypes.FRIEND_ACCEPT,
        data={"accepter_id": str(user.id)},
    )
    return True


def reject_friend_request(user, friend_request):
    if friend_request.receiver != user:
        raise PermissionDenied("Not authorized")
    if friend_request.status != "pending":
        raise ValidationError("Request already processed")

    # Delete the request to keep the database clean
    friend_request.delete()
    return friend_request


def cancel_friend_request(user, friend_request):
    if friend_request.sender != user:
        raise PermissionDenied("Not authorized")
    if friend_request.status != "pending":
        raise ValidationError("Cannot cancel processed request")

    # Delete the pending request
    friend_request.delete()
    return True


def remove_friend(user, friend_id):
    try:
        friend = User.objects.get(id=friend_id)
    except User.DoesNotExist:
        raise NotFound("User not found")

    # Delete the Friendship record
    deleted, _ = Friendship.objects.filter(
        Q(sender=user, receiver=friend) | Q(sender=friend, receiver=user)
    ).delete()

    if deleted == 0:
        raise NotFound("Friendship not found")

    # Invalidate messaging permission cache
    _invalidate_message_permission(user.id, friend.id)

    # Also clean up any lingering FriendRequests
    FriendRequest.objects.filter(
        Q(sender=user, receiver=friend) | Q(sender=friend, receiver=user)
    ).delete()

    return True


def block_user(blocker, blocked_user_id):
    try:
        blocked_user = User.objects.get(id=blocked_user_id)
    except User.DoesNotExist:
        raise NotFound("User not found")

    UserBlock.objects.get_or_create(blocker=blocker, blocked_user=blocked_user)

    # Invalidate messaging permission cache
    _invalidate_message_permission(blocker.id, blocked_user.id)

    # Remove friendship if exists
    Friendship.objects.filter(
        Q(sender=blocker, receiver=blocked_user)
        | Q(sender=blocked_user, receiver=blocker)
    ).delete()

    # Cancel pending requests
    FriendRequest.objects.filter(
        Q(sender=blocker, receiver=blocked_user) | Q(sender=blocked_user, receiver=blocker),
        status="pending",
    ).delete()
    return True


def unblock_user(blocker, blocked_user_id):
    deleted, _ = UserBlock.objects.filter(
        blocker=blocker, blocked_user_id=blocked_user_id
    ).delete()
    if deleted == 0:
        raise NotFound("Block record not found")
    # Invalidate messaging permission cache
    _invalidate_message_permission(blocker.id, blocked_user_id)
    return True


def get_nearby_users(
    current_user,
    user_type=None,
    radius=50.0,
    search_query="",
    include_friends=True,
    city=None,
    state=None,
):
    user_point = None

    if hasattr(current_user, "profile") and current_user.profile.location_point:
        user_point = current_user.profile.location_point

    # Exclude blocked users
    blocked_ids = list(
        UserBlock.objects.filter(blocker=current_user).values_list(
            "blocked_user_id", flat=True
        )
    )
    blocked_by_ids = list(
        UserBlock.objects.filter(blocked_user=current_user).values_list(
            "blocker_id", flat=True
        )
    )

    # Exclude existing friends
    friendships = Friendship.objects.filter(Q(sender=current_user) | Q(receiver=current_user))
    friend_ids = [
        f.receiver_id if f.sender_id == current_user.id else f.sender_id
        for f in friendships
    ]

    exclude_ids = set(blocked_ids + blocked_by_ids)
    if not include_friends:
        exclude_ids.update(friend_ids)

    users_query = User.objects.select_related("profile").filter(is_active=True).exclude(
        id__in=exclude_ids
    )

    if user_type:
        users_query = users_query.filter(user_type=user_type)

    if city:
        users_query = users_query.filter(profile__city__icontains=city)

    if state:
        users_query = users_query.filter(profile__state__icontains=state)

    if search_query:
        users_query = users_query.filter(
            Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(username__icontains=search_query)
        )

    if user_point:
        # Distance calculation
        if radius:
            users_query = users_query.filter(
                profile__location_point__distance_lte=(user_point, D(mi=radius))
            )

        return users_query.annotate(
            distance=Distance("profile__location_point", user_point)
        ).order_by("distance")
    else:
        # Global search result
        return users_query.select_related("profile")[:100]


def get_suggested_friends(current_user, limit=20):
    from django.db.models import Count, IntegerField, F, FloatField, ExpressionWrapper

    user_point = None
    if hasattr(current_user, "profile") and current_user.profile.location_point:
        user_point = current_user.profile.location_point

    # 1. Gather exclusions via DB Subqueries to avoid loading ANY lists into Python memory
    blocked_ids = UserBlock.objects.filter(blocker=current_user).values("blocked_user_id")
    blocked_by_ids = UserBlock.objects.filter(blocked_user=current_user).values("blocker_id")
    pending_sent = FriendRequest.objects.filter(sender=current_user, status="pending").values("receiver_id")
    pending_received = FriendRequest.objects.filter(receiver=current_user, status="pending").values("sender_id")
    
    # friend_ids need Python map because Friendship model stores users dynamically as sender/receiver
    friendships = Friendship.objects.filter(Q(sender=current_user) | Q(receiver=current_user))
    friend_ids = [f.receiver_id if f.sender_id == current_user.id else f.sender_id for f in friendships]

    # 2. Base Queryset (select_related fixes N+1 query)
    users_query = User.objects.select_related("profile").filter(
        is_active=True
    ).exclude(
        Q(id__in=blocked_ids) |
        Q(id__in=blocked_by_ids) |
        Q(id__in=pending_sent) |
        Q(id__in=pending_received) |
        Q(id__in=friend_ids) |
        Q(id=current_user.id)
    )

    # 3. Annotate count in DB (memory efficient)
    users_query = users_query.annotate(
        mutual_friends_initiated=Count(
            "friendships_initiated",
            filter=Q(friendships_initiated__receiver_id__in=friend_ids),
            distinct=True
        ),
        mutual_friends_received=Count(
            "friendships_received",
            filter=Q(friendships_received__sender_id__in=friend_ids),
            distinct=True
        )
    ).annotate(
        mutual_friends_count=ExpressionWrapper(
            F("mutual_friends_initiated") + F("mutual_friends_received"),
            output_field=IntegerField()
        )
    )

    # 4. Sorting exclusively in DB instead of Python so we can safely yield/paginate
    if user_point:
        users_query = users_query.annotate(
            distance=Distance("profile__location_point", user_point)
        ).order_by("-mutual_friends_count", "distance")
    else:
        users_query = users_query.order_by("-mutual_friends_count")

    # Return the raw QuerySet for the View to lazily evaluate via Pagination!
    # By returning this, the DB handles chunk sizes, counting, and slicing effortlessly.
    return users_query


def get_users_near_map_point(
    current_user,
    latitude: float,
    longitude: float,
    radius: float = 25.0,
    user_type: str = None,
    search_query: str = "",
    include_friends: bool = True,
):
    """
    Find users near a specific map coordinate (lat/lng) selected by the client.

    Unlike `get_nearby_users()` which uses the logged-in user's own stored
    location as the center, this function accepts an *arbitrary* map point
    chosen by the client — enabling the "tap anywhere on the map to see who
    is nearby" flow.

    Args:
        current_user   : The requesting user (used to apply block/friend filters).
        latitude       : WGS-84 latitude of the center point chosen on the map.
        longitude      : WGS-84 longitude of the center point chosen on the map.
        radius         : Search radius in miles (default 25 mi).
        user_type      : Optional filter — 'patpal' | 'patnabor' | None (all).
        search_query   : Optional text search on first_name / last_name / username.
        include_friends: Whether to include already-friended users in results.

    Returns:
        QuerySet[User] annotated with `distance` (Distance object), ordered
        nearest-first.  The QuerySet is lazy — pagination is handled by the view.
    """
    # Build a PostGIS Point from the client-supplied coordinates.
    # SRID 4326 = WGS-84 (standard GPS / web-map coordinate system).
    map_point = Point(longitude, latitude, srid=4326)

    # ── Block exclusions (bidirectional) ─────────────────────────────────────
    blocked_ids     = UserBlock.objects.filter(blocker=current_user).values("blocked_user_id")
    blocked_by_ids  = UserBlock.objects.filter(blocked_user=current_user).values("blocker_id")

    # ── Friend exclusions (optional) ─────────────────────────────────────────
    friendships = Friendship.objects.filter(Q(sender=current_user) | Q(receiver=current_user))
    friend_ids  = [
        f.receiver_id if f.sender_id == current_user.id else f.sender_id
        for f in friendships
    ]

    # ── Base queryset ─────────────────────────────────────────────────────────
    users_qs = (
        User.objects
        .select_related("profile")
        .filter(
            is_active=True,
            # Only include users who have a stored GPS location — users without
            # a location_point cannot appear on the map anyway.
            profile__location_point__isnull=False,
        )
        .exclude(id=current_user.id)
        .exclude(id__in=blocked_ids)
        .exclude(id__in=blocked_by_ids)
    )

    if not include_friends and friend_ids:
        users_qs = users_qs.exclude(id__in=friend_ids)

    # ── Optional filters ──────────────────────────────────────────────────────
    if user_type:
        users_qs = users_qs.filter(user_type=user_type)

    if search_query:
        users_qs = users_qs.filter(
            Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(username__icontains=search_query)
        )

    # ── Spatial radius filter + distance annotation ───────────────────────────
    users_qs = (
        users_qs
        .filter(profile__location_point__distance_lte=(map_point, D(mi=radius)))
        .annotate(distance=Distance("profile__location_point", map_point))
        .order_by("distance")  # nearest first
    )

    return users_qs


def get_users_in_bbox(
    current_user,
    min_lat: float,
    max_lat: float,
    min_lng: float,
    max_lng: float,
    user_type: str = None,
    search_query: str = "",
    include_friends: bool = True,
    limit: int = 300,
):
    """
    Find users within a map viewport bounding box (for pan/zoom flows).

    The frontend sends the 4 corners of the currently visible map area.
    The backend returns ALL users inside that rectangle — no page numbers.
    When the user pans or zooms the map, the frontend re-calls this endpoint
    with the new viewport coordinates.

    Args:
        current_user : The requesting user (for block/friend filters).
        min_lat      : South boundary of the viewport.
        max_lat      : North boundary of the viewport.
        min_lng      : West  boundary of the viewport.
        max_lng      : East  boundary of the viewport.
        user_type    : Optional 'patpal' | 'patnabor' | None.
        search_query : Optional text search.
        include_friends : Include already-friended users.
        limit        : Hard cap on returned results (default 300, max 500).

    Returns:
        QuerySet[User] with `distance` annotated from the viewport center,
        ordered nearest-to-center first. Sliced to `limit`.
    """
    from django.contrib.gis.geos import Polygon

    # Rectangular polygon matching the visible map area.
    # from_bbox() takes (min_lng, min_lat, max_lng, max_lat).
    viewport_polygon = Polygon.from_bbox((min_lng, min_lat, max_lng, max_lat))
    viewport_polygon.srid = 4326

    # Centre of viewport — used for distance ordering so nearest pins come first
    center_point = Point(
        (min_lng + max_lng) / 2,
        (min_lat + max_lat) / 2,
        srid=4326,
    )

    # ── Block exclusions (bidirectional) ─────────────────────────────────────
    blocked_ids    = UserBlock.objects.filter(blocker=current_user).values("blocked_user_id")
    blocked_by_ids = UserBlock.objects.filter(blocked_user=current_user).values("blocker_id")

    # ── Friend exclusions (optional) ─────────────────────────────────────────
    friendships = Friendship.objects.filter(Q(sender=current_user) | Q(receiver=current_user))
    friend_ids  = [
        f.receiver_id if f.sender_id == current_user.id else f.sender_id
        for f in friendships
    ]

    # ── Base queryset ─────────────────────────────────────────────────────────
    users_qs = (
        User.objects
        .select_related("profile")
        .filter(
            is_active=True,
            profile__location_point__isnull=False,
            # Spatial filter: user's pin must be INSIDE the viewport polygon
            profile__location_point__within=viewport_polygon,
        )
        .exclude(id=current_user.id)
        .exclude(id__in=blocked_ids)
        .exclude(id__in=blocked_by_ids)
    )

    if not include_friends and friend_ids:
        users_qs = users_qs.exclude(id__in=friend_ids)

    if user_type:
        users_qs = users_qs.filter(user_type=user_type)

    if search_query:
        users_qs = users_qs.filter(
            Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(username__icontains=search_query)
        )

    # Annotate distance from viewport center → nearest first
    users_qs = (
        users_qs
        .annotate(distance=Distance("profile__location_point", center_point))
        .order_by("distance")
    )

    # Safety cap — never flood the client with thousands of pins at once
    limit = min(limit, 500)
    return users_qs[:limit]
