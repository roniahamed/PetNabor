from django.utils.safestring import mark_safe
from .models import SiteSettings

def site_title_callback(request):
    try:
        settings = SiteSettings.objects.first()
        if settings and settings.site_name:
            return f"{settings.site_name} Admin"
    except Exception:
        pass
    return "PetNabor Admin"

def site_header_callback(request):
    try:
        settings = SiteSettings.objects.first()
        if settings and settings.site_name:
            return settings.site_name
    except Exception:
        pass
    return "PetNabor"
