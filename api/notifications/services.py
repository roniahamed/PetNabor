"""
Services for sending push and in-app notifications.

Handles batching and asynchronous processing via Celery.
"""
from celery import shared_task
from firebase_admin import messaging, exceptions
from django.contrib.auth import get_user_model
from django.db.models import Q
from .models import FCMDevice, Notifications, NotificationTypes

User = get_user_model()

# Map notification types to their required setting field
NOTIFICATION_SETTINGS_MAP = {
    NotificationTypes.FRIEND_REQUEST: "friend_request_notifications",
    NotificationTypes.FRIEND_ACCEPT: "friend_request_notifications",
    NotificationTypes.LIKE: "like_notifications",
    NotificationTypes.COMMENT: "comment_notifications",
    NotificationTypes.MENTION: "mention_notifications",
    NotificationTypes.MEETUP_INVITE: "meetup_notifications",
    NotificationTypes.MEETUP_UPDATE: "meetup_notifications",
    NotificationTypes.SYSTEM: "system_notifications",
    NotificationTypes.PROMOTION: "marketing_notifications",
    NotificationTypes.MARKETING: "marketing_notifications",
    NotificationTypes.REWARD: "marketing_notifications",
    NotificationTypes.REFERRAL_BONUS: "marketing_notifications",
    NotificationTypes.STREAK_BONUS: "marketing_notifications",
    NotificationTypes.MESSAGE: "message_notifications",
}

DEFAULT_BATCH_SIZE = 500


def send_notification(
    title,
    body,
    user_id=None,
    user_ids=None,
    broadcast=False,
    data=None,
    notification_type=NotificationTypes.INFO,
    filters=None,
):
    """
    Unified entrypoint for triggering notifications.
    Handles single user, multi-user, and broadcast efficiently while pushing heavy work to Celery.
    """
    users_query = User.objects.all()

    if broadcast:
        if filters:
            users_query = users_query.filter(**filters)
    elif user_id:
        users_query = users_query.filter(id=user_id)
    elif user_ids:
        users_query = users_query.filter(id__in=user_ids)
    else:
        return "No target users provided."

    # Pre-filter by user's specific notification setting to minimize database queries in the batch
    setting_field = NOTIFICATION_SETTINGS_MAP.get(notification_type)
    if setting_field:
        users_query = users_query.filter(
            **{f"notification_settings__{setting_field}": True}
        )

    total_count = users_query.count()
    if total_count == 0:
        return "No active users found with the required settings."

    batch_size = DEFAULT_BATCH_SIZE
    users_query = users_query.order_by("id")

    batch_ids = []
    # Using iterator(chunk_size=batch_size) is more efficient for very large datasets
    for user_id in users_query.values_list("id", flat=True).iterator(
        chunk_size=batch_size
    ):
        batch_ids.append(user_id)
        if len(batch_ids) >= batch_size:
            _process_notification_batch.delay(
                batch_ids, title, body, data, notification_type
            )
            batch_ids = []

    if batch_ids:
        _process_notification_batch.delay(
            batch_ids, title, body, data, notification_type
        )

    return f"Notification queued for {total_count} users."


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def _process_notification_batch(
    self, user_ids, title, body, data=None, notification_type=NotificationTypes.INFO
):
    """Celery task to handle the actual creation of DB records and FCM sending."""
    try:
        # Filter out user_ids that do not exist in the DB to avoid ForeignKeyViolation
        existing_user_ids = set(User.objects.filter(id__in=user_ids).values_list("id", flat=True))

        # Create In-App Notifications
        notifications_to_create = []
        for uid in existing_user_ids:
            try:
                notifications_to_create.append(
                    Notifications(
                        user_id=uid,
                        title=title,
                        body=body,
                        data=data or {},
                        notification_type=notification_type,
                    )
                )
            except Exception as e:
                pass

        if notifications_to_create:
            Notifications.objects.bulk_create(
                notifications_to_create, ignore_conflicts=True
            )

        users_with_push = User.objects.filter(
            id__in=user_ids, notification_settings__push_notifications=True
        )
        push_user_ids = list(users_with_push.values_list("id", flat=True))

        if not push_user_ids:
            return "Batch Processed: DB records created, but no users had push enabled."

        tokens = list(
            FCMDevice.objects.filter(user_id__in=push_user_ids).values_list(
                "registration_id", flat=True
            )
        )

        if not tokens:
            return "Batch Processed: DB records created, but no FCM tokens found for the push-enabled users."

        payload_data = {"type": notification_type}
        if data:
            payload_data.update({k: str(v) for k, v in data.items()})

        android_config = messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                priority="high",
                sound="default",
                channel_id="high-priority",
                default_vibrate_timings=True,
                default_sound=True,
            ),
        )

        apns_config = messaging.APNSConfig(
            headers={"apns-priority": "10"},
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    alert=messaging.ApsAlert(title=title, body=body),
                    badge=1,
                    sound="default",
                    content_available=True,
                )
            ),
        )

        webpush_config = messaging.WebpushConfig(
            headers={"Urgency": "high"},
            notification=messaging.WebpushNotification(
                title=title,
                body=body,
                icon="/static/icons/notification-icon.png",
            ),
        )

        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data=payload_data,
            tokens=tokens,
            android=android_config,
            apns=apns_config,
            webpush=webpush_config,
        )

        response = messaging.send_each_for_multicast(message)

        if response.failure_count > 0:
            invalid_tokens = []
            for idx, resp in enumerate(response.responses):
                if not resp.success:
                    err = resp.exception
                    if isinstance(
                        err,
                        (
                            exceptions.InvalidArgumentError,
                            exceptions.NotFoundError,
                            exceptions.UnregisteredError,
                        ),
                    ):
                        invalid_tokens.append(tokens[idx])
            if invalid_tokens:
                FCMDevice.objects.filter(registration_id__in=invalid_tokens).delete()

        return f"Batch Processed: {response.success_count} sent, {response.failure_count} failed."

    except Exception as exc:
        raise self.retry(exc=exc)
