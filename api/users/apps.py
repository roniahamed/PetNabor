from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = 'api.users'

    def ready(self):
        import api.users.signals  # noqa: F401

        # No more monkey patching ModelAdmin here. It is handled by UUIDSearchMixin.
        pass
