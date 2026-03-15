from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch
from .services import send_notification
from .models import NotificationSettings, NotificationTypes

User = get_user_model()

class NotificationServiceTests(TestCase):
    def setUp(self):
        # Create users with allowed notification settings
        self.users = []
        for i in range(10):
            user = User.objects.create_user(username=f'user{i}', email=f'user{i}@example.com', password='password')
            # Assuming NotificationSettings are created automatically via signal or manually
            # Let's ensure they exist and have the right settings
            settings, created = NotificationSettings.objects.get_or_create(user=user)
            settings.system_notifications = True
            settings.save()
            self.users.append(user)

    @patch('api.notifications.services._process_notification_batch.delay')
    def test_send_notification_chunking(self, mock_delay):
        # Test with a small batch size for verification
        with patch('api.notifications.services.DEFAULT_BATCH_SIZE', 3):

            result = send_notification(
                title="Test Title",
                body="Test Body",
                broadcast=True,
                notification_type=NotificationTypes.SYSTEM
            )
            
            # 10 users / batch_size 3 = 4 batches (3, 3, 3, 1)
            self.assertEqual(mock_delay.call_count, 4)
            self.assertIn("queued for 10 users", result)

    @patch('api.notifications.services._process_notification_batch.delay')
    def test_send_notification_no_users(self, mock_delay):
        # Disable notifications for all users
        NotificationSettings.objects.all().update(system_notifications=False)
        
        result = send_notification(
            title="Test Title",
            body="Test Body",
            broadcast=True,
            notification_type=NotificationTypes.SYSTEM
        )
        
        self.assertEqual(mock_delay.call_count, 0)
        self.assertEqual(result, "No active users found with the required settings.")

