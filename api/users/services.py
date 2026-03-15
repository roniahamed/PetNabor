from firebase_admin import auth
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
import uuid

from api.notifications.services import send_notification
from api.notifications.models import NotificationTypes

User = get_user_model()


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def firebase_login_service(
    id_token,
    first_name="",
    last_name="",
    user_type="patnabor",
    agree_to_terms_and_conditions=False,
):
    try:
        decoded_token = auth.verify_id_token(id_token)

        uid = decoded_token.get("uid")
        email = decoded_token.get("email")
        phone = decoded_token.get("phone_number")

        firebase_name = decoded_token.get("name", "")

        if not uid:
            raise ValueError("Invalid Firebase token: Missing UID")

        if firebase_name and not first_name:
            name_parts = firebase_name.split(" ", 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ""

        user = User.objects.filter(firebase_uid=uid).first()

        if not email and not phone:
            raise ValueError("Invalid Firebase token: Missing email or phone number")

        if not user:
            if email:
                user = User.objects.filter(email=email).first()
            elif phone:
                user = User.objects.filter(phone=phone).first()

        if user:
            if not user.firebase_uid:
                user.firebase_uid = uid
                user.save(update_fields=["firebase_uid"])

        else:
            base_username = (
                email.split("@")[0] if email else f"user_{str(uuid.uuid4())[:8]}"
            )

            user = User.objects.create(
                email=email,
                username=base_username,
                phone=phone,
                first_name=first_name,
                last_name=last_name,
                user_type=user_type,
                agree_to_terms_and_conditions=agree_to_terms_and_conditions,
                firebase_uid=uid,
                is_verified=True,
                is_active=True,
                is_staff=False,
                is_superuser=False,
                is_patpal=False,
                is_online=False,
                last_active=None,
            )

            user.set_unusable_password()
            user.save()

        tokens = get_tokens_for_user(user)
        
        send_notification(
            user_id=user.id,
            title="New Login Detected",
            body="A new login session was established for your account.",
            data={"type": "login"},
            notification_type=NotificationTypes.LOGIN
        )

        return tokens, user
    except Exception as e:
        raise ValueError(f"Authentication Failed: {str(e)}")
