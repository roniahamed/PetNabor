"""
Serializers for the authentication system.

Clean validation using DRY validators from validators.py.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Profile
from .validators import (
    validate_email_format,
    validate_password_strength,
    validate_phone_number,
    validate_signup_identifier,
)

User = get_user_model()


# ──────────────────────────────────────────────
# Auth Serializers
# ──────────────────────────────────────────────


class SignupSerializer(serializers.Serializer):
    """Validates signup data. Requires at least email or phone."""

    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=15)
    password = serializers.CharField(required=True, write_only=True, min_length=8)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    user_type = serializers.CharField(required=False, default="patnabor")
    agree_to_terms_and_conditions = serializers.BooleanField(
        required=False, default=False
    )

    def validate_email(self, value):
        if value:
            return validate_email_format(value)
        return value

    def validate_phone(self, value):
        if value:
            return validate_phone_number(value)
        return value

    def validate_password(self, value):
        return validate_password_strength(value)

    def validate(self, attrs):
        email = attrs.get("email")
        phone = attrs.get("phone")
        validate_signup_identifier(email, phone)
        return attrs


class LoginSerializer(serializers.Serializer):
    """Validates login credentials. Accepts email or phone + password."""

    email_or_phone = serializers.CharField(
        required=True,
        help_text="Email address or phone number.",
    )
    password = serializers.CharField(required=True, write_only=True)

    def validate_email_or_phone(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Email or phone number is required.")
        return value.strip()


class VerifyPhoneOTPSerializer(serializers.Serializer):
    """Validates phone OTP verification request."""

    phone = serializers.CharField(required=True, max_length=15)
    otp_code = serializers.CharField(required=True, min_length=4, max_length=6)

    def validate_phone(self, value):
        return validate_phone_number(value)

    def validate_otp_code(self, value):
        if not value or not value.strip().isdigit():
            raise serializers.ValidationError("OTP code must contain only digits.")
        return value.strip()


class VerifyEmailOTPSerializer(serializers.Serializer):
    """Validates email OTP verification request."""

    email = serializers.EmailField(required=True)
    otp_code = serializers.CharField(required=True, min_length=4, max_length=6)

    def validate_email(self, value):
        return validate_email_format(value)

    def validate_otp_code(self, value):
        if not value or not value.strip().isdigit():
            raise serializers.ValidationError("OTP code must contain only digits.")
        return value.strip()


class ResendOTPSerializer(serializers.Serializer):
    """Validates resend OTP request for phone."""

    phone = serializers.CharField(required=True, max_length=15)

    def validate_phone(self, value):
        return validate_phone_number(value)


class ResendEmailOTPSerializer(serializers.Serializer):
    """Validates resend OTP request for email."""

    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        return validate_email_format(value)


class RequestPasswordResetSerializer(serializers.Serializer):
    """Validates password reset request."""

    email_or_phone = serializers.CharField(required=True)

    def validate_email_or_phone(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Email or phone number is required.")
        return value.strip()


class ConfirmPasswordResetSerializer(serializers.Serializer):
    """Validates password reset confirmation."""

    email_or_phone = serializers.CharField(required=True)
    otp_code = serializers.CharField(required=True, min_length=4, max_length=6)
    new_password = serializers.CharField(required=True, write_only=True, min_length=8)

    def validate_email_or_phone(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Email or phone number is required.")
        return value.strip()

    def validate_otp_code(self, value):
        if not value or not value.strip().isdigit():
            raise serializers.ValidationError("OTP code must contain only digits.")
        return value.strip()

    def validate_new_password(self, value):
        return validate_password_strength(value)


# ──────────────────────────────────────────────
# Firebase Serializer
# ──────────────────────────────────────────────


class FirebaseTokenSerializer(serializers.Serializer):
    """Validates Firebase login token request."""

    id_token = serializers.CharField(required=True, help_text="Firebase ID Token")
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    user_type = serializers.CharField(required=False, default="patnabor")
    agree_to_terms_and_conditions = serializers.BooleanField(
        required=False, default=False
    )


# ──────────────────────────────────────────────
# Data Serializers
# ──────────────────────────────────────────────


class Profile_Read(serializers.ModelSerializer):
    """Profile model serializer with read-only fields."""

    class Meta:
        model = Profile
        fields = [
            "address_street",
            "city",
            "state",
            "zipcode",
            "location_point",
            "date_of_birth",
            "profile_picture",
            "cover_photo",
            "bio",
            "referral_code",
            "referred_by",
        ]
        read_only_fields = [
            "address_street",
            "city",
            "state",
            "zipcode",
            "location_point",
            "date_of_birth",
            "profile_picture",
            "cover_photo",
            "bio",
            "referral_code",
            "referred_by",
        ]


class UserSerializer(serializers.ModelSerializer):
    profile = Profile_Read(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "phone",
            "first_name",
            "last_name",
            "user_type",
            "is_verified",
            "is_email_verified",
            "is_phone_verified",
            "is_active",
            "is_staff",
            "is_superuser",
            "created_at",
            "agree_to_terms_and_conditions",
            "is_patpal",
            "is_online",
            "last_active",
            "firebase_uid",
            "profile",
            "username",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_verified",
            "is_email_verified",
            "is_phone_verified",
            "is_active",
            "is_staff",
            "is_superuser",
            "created_at",
            "email",
            "phone",
            "updated_at",
            "firebase_uid",
            "username",
        ]


class ProfileSerializer(serializers.ModelSerializer):
    """Profile model serializer. Allows updating user first_name and last_name also."""

    first_name = serializers.CharField(source="user.first_name", required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(source="user.last_name", required=False, allow_blank=True, max_length=150)

    class Meta:
        model = Profile
        fields = [
            "id",
            "user",
            "first_name",
            "last_name",
            "address_street",
            "city",
            "state",
            "zipcode",
            "location_point",
            "date_of_birth",
            "profile_picture",
            "cover_photo",
            "bio",
            "referral_code",
            "referred_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "created_at",
            "updated_at",
            "referral_code",
            "referred_by",
        ]

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        
        # Update user fields if provided
        if "first_name" in user_data or "last_name" in user_data:
            user = instance.user
            if "first_name" in user_data:
                user.first_name = user_data["first_name"]
            if "last_name" in user_data:
                user.last_name = user_data["last_name"]
            user.save(update_fields=["first_name", "last_name"])

        # Update profile fields
        return super().update(instance, validated_data)
