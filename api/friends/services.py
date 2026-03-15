from django.db.models import Q
from django.contrib.auth import get_user_model
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied
from .models import FriendRequest, Friendship, UserBlock
from api.notifications.services import send_notification
from api.notifications.models import NotificationTypes

User = get_user_model()


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
        # Automatically accept
        reverse_req.status = "accepted"
        reverse_req.save()
        Friendship.objects.create(sender=receiver, receiver=sender)

        # Notify the original sender that their request was accepted
        send_notification(
            user_id=receiver.id,
            title="Friend Request Accepted",
            body=f"{sender.username} accepted your friend request.",
            notification_type=NotificationTypes.FRIEND_ACCEPT,
        )
        return reverse_req, True  # True means automatically accepted

    freq = FriendRequest.objects.create(sender=sender, receiver=receiver, status="pending")

    # Notify the receiver about the new friend request
    send_notification(
        user_id=receiver.id,
        title="New Friend Request",
        body=f"{sender.username} sent you a friend request.",
        notification_type=NotificationTypes.FRIEND_REQUEST,
    )
    return freq, False


def accept_friend_request(user, friend_request):
    if friend_request.receiver != user:
        raise PermissionDenied("Not authorized")
    if friend_request.status != "pending":
        raise ValidationError("Request already processed")

    if is_blocked(user, friend_request.sender):
        raise ValidationError("Cannot accept request, user is blocked")

    friend_request.status = "accepted"
    friend_request.save()
    Friendship.objects.get_or_create(
        sender=friend_request.sender, receiver=friend_request.receiver
    )

    # Notify the sender that the request was accepted
    send_notification(
        user_id=friend_request.sender_id,
        title="Friend Request Accepted",
        body=f"{user.username} accepted your friend request.",
        notification_type=NotificationTypes.FRIEND_ACCEPT,
    )
    return friend_request


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
