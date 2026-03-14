from django.db import models
import uuid
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.contrib.gis.db import models as gis_models
import os
from django.conf import settings


class CustomUserManager(BaseUserManager):
    def create_user(self, email=None, phone=None, password=None, **extra_fields):
        if not email and not phone:
            raise ValueError("The Email or Phone number must be set")

        email = self.normalize_email(email) if email else None

        if "username" in extra_fields and not extra_fields["username"]:
            extra_fields.pop("username")

        user = self.model(email=email, phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email=email, password=password, **extra_fields)


class UserTypes(models.TextChoices):
    PATNABOR = "patnabor", "Patnabor"
    PATPAL = "patpal", "Patpal"
    VENDOR = "vendor", "Vendor"
    ADMIN = "admin", "Admin"


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    email = models.EmailField(unique=True, null=True, blank=True)
    phone = models.CharField(max_length=15, unique=True, null=True, blank=True)

    first_name = models.CharField(max_length=150, blank=True, null=True)
    last_name = models.CharField(max_length=150, blank=True, null=True)

    user_type = models.CharField(
        max_length=20, choices=UserTypes.choices, default=UserTypes.PATNABOR
    )
    agree_to_terms_and_conditions = models.BooleanField(default=False)
    firebase_uid = models.CharField(max_length=255, unique=True, null=True, blank=True)

    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    is_patpal = models.BooleanField(default=False)
    is_online = models.BooleanField(default=False)
    last_active = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    password = models.CharField(max_length=128, null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = [
        "username",
    ]
    
    class Meta:
        indexes = [
            models.Index(fields=['user_type', 'is_active']),
            models.Index(fields=['firebase_uid']),
        ]

    objects = CustomUserManager()

    def __str__(self):
        return self.email if self.email else self.phone

    @property
    def currently_online(self):
        if self.last_active:
            from django.utils import timezone

            return (timezone.now() - self.last_active).total_seconds() < 300
        return False


def profile_image_path(instance, filename):
    ext = filename.split(".")[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join("profiles/images/", filename)


class Profile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )

    address_street = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    zipcode = models.CharField(max_length=20, null=True, blank=True)

    location_point = gis_models.PointField(srid=4326, null=True, blank=True)

    date_of_birth = models.DateField(null=True, blank=True)
    profile_picture = models.ImageField(
        upload_to=profile_image_path, null=True, blank=True
    )
    cover_photo = models.ImageField(upload_to=profile_image_path, null=True, blank=True)
    bio = models.TextField(null=True, blank=True)

    referral_code = models.CharField(max_length=50, unique=True, null=True, blank=True)
    referred_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referrals",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile of {self.user.email}"
