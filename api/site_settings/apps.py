from django.apps import AppConfig


class SiteSettingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.site_settings'
    verbose_name = 'Site Settings'
