# from asyncio import exceptions
from celery import shared_task
from firebase_admin import messaging, exceptions
from .models import FCMDevice, Notifications
from django.contrib.auth import get_user_model

User = get_user_model()


# Send push notification to specific users


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def send_push_notification(self, user_ids, title, body, data=None, notification_type='info'):

    try: 
        notifications_to_create = []

        for user_id in user_ids:
             notifications_to_create.append( Notifications(
                user_id=user_id,
                title=title,
                body=body,
                data=data or {},
                notification_type=notification_type,
            ))
        
        Notifications.objects.bulk_create(notifications_to_create)
        

        devices = FCMDevice.objects.filter(user_id__in=user_ids)

        tokens = [device.registration_id for device in devices]
        if not tokens:
            return f"No devices registered for users with ids {user_ids}."
        
        payload_data = {
            'type': notification_type,
        }
        if data:
            for k, v in data.items():
                payload_data[k] = str(v)

        
        android_config = messaging.AndroidConfig(
            priority='high',
            notification=messaging.AndroidNotification(
                priority='high',
                sound='default',
                channel_id='high-priority',
                default_vibrate_timings=True,
                default_sound=True,
            )
        )

        apns_config = messaging.APNSConfig(
            headers={'apns-priority': '10'},

            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    alert=messaging.ApsAlert(
                        title=title,
                        body=body
                    ),
                    badge=1,
                    sound='default',
                    content_available=True,
                )
            )
        )

        webpush_config = messaging.WebpushConfig(
                headers={'Urgency': 'high'},
                notification=messaging.WebpushNotification(
                    title=title,
                    body=body,
                    icon='/static/icons/notification-icon.png',
                )
        )


        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=title,
                body=body
                ),
                data=payload_data,
                tokens=tokens,
                android=android_config,
                apns=apns_config,
                webpush=webpush_config
            )
        
        response = messaging.send_each_for_multicast(message)


        if response.failure_count > 0:
            invalid_tokens = []
            for idx, resp in enumerate(response.responses):
                if not resp.success:
                    err = resp.exception
                    if isinstance(err, (exceptions.InvalidArgumentError, exceptions.NotFoundError)):
                         invalid_tokens.append(tokens[idx])
            if invalid_tokens:
                FCMDevice.objects.filter(registration_id__in=invalid_tokens).delete()

        return f"Batch Processed: {response.success_count} sent, {response.failure_count} failed."

    except Exception as exc:
        raise self.retry(exc=exc)
    


# Send broadcast notification to all users

@shared_task
def send_broadcast_notification(title, body, data=None, notification_type='info', filters = None):
    users = User.objects.all().select_related('notification_settings').order_by('id')
    if filters:
        users = users.filter(**filters, notification_settings__receive_push_notifications=True)
    
    
    if notification_type in ['reword_available', 'referral_bonus', 'streak_bonus', '']:
        users = users.filter(notification_settings__notify_when_reword_available=True)
    if notification_type in ['promotion', 'marketing']:
        users = users.filter(notification_settings__marketing_notifications=True)
    
    
    total_users = users.count()

    if not total_users:
        return "No users found for the given filters."

    batch_size = 500

    for offset in range(0, total_users, batch_size):
        batch_ids = list(users.values_list('id', flat=True)[offset:offset + batch_size])
        if batch_ids:
            send_push_notification.delay(batch_ids, title, body, data, notification_type)
    
    return f"Broadcast started for {total_users} users."





