from django.apps import AppConfig


class ReferralConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.referral'

    def ready(self):
        import api.referral.signals  # noqa: F401
