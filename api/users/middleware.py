from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from rest_framework_simplejwt.authentication import JWTAuthentication


class UpdateLastActiveMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if not request.user.is_authenticated:
           
            try:
                header = JWTAuthentication().get_header(request)
                if header:
                    raw_token = JWTAuthentication().get_raw_token(header)
                    validated_token = JWTAuthentication().get_validated_token(raw_token)
                    user = JWTAuthentication().get_user(validated_token)
                    request.user = user
            except Exception:
                pass
        if request.user.is_authenticated:
            # print(f"Updating last active for user: {request.user.email}")
            request.user.last_active = timezone.now()
            request.user.is_online = True
            request.user.save(update_fields=['last_active', 'is_online'])
        return None