from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    name = 'api.notifications'
    
    def ready(self):
        import api.notifications.signals  # noqa: F401

