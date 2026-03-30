"""
Validation utilities for the users app.
"""

import re

from django.core.validators import validate_email as django_validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError


# E.164 phone format: +[country code][number], 7-15 digits total
PHONE_REGEX = re.compile(r"^\+[1-9]\d{6,14}$")

# Password: minimum 8 chars, at least 1 uppercase, 1 lowercase, 1 digit
PASSWORD_REGEX = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$")


def validate_phone_number(phone):
    """
    Validate phone number is in E.164 format (e.g., +1234567890).

    Raises:
        ValidationError: If the phone number format is invalid.
    """
    if not phone:
        raise ValidationError({"phone": "Phone number is required."})

    phone = phone.strip()
    if not PHONE_REGEX.match(phone):
        raise ValidationError(
            {"phone": "Phone number must be in E.164 format (e.g., +1234567890)."}
        )
    return phone


def validate_password_strength(password):
    """
    Validate password meets minimum strength requirements.

    Requirements:
        - At least 8 characters
        - At least 1 uppercase letter
        - At least 1 lowercase letter
        - At least 1 digit

    Raises:
        ValidationError: If the password does not meet requirements.
    """
    if not password:
        raise ValidationError({"password": "Password is required."})

    if len(password) < 8:
        raise ValidationError(
            {"password": "Password must be at least 8 characters long."}
        )

    if not PASSWORD_REGEX.match(password):
        raise ValidationError(
            {
                "password": (
                    "Password must contain at least 1 uppercase letter, "
                    "1 lowercase letter, and 1 digit."
                )
            }
        )
    return password


def validate_email_format(email):
    """
    Validate email using Django's built-in email validator with clearer messages.

    Raises:
        ValidationError: If the email format is invalid.
    """
    if not email:
        raise ValidationError({"email": "Email address is required."})

    email = email.strip().lower()
    try:
        django_validate_email(email)
    except DjangoValidationError:
        raise ValidationError({"email": "Please enter a valid email address."})

    return email


def validate_signup_identifier(email, phone):
    """
    Ensure at least one of email or phone is provided for signup.

    Raises:
        ValidationError: If neither email nor phone is provided.
    """
    if not email and not phone:
        raise ValidationError(
            {"detail": "Either email or phone number is required to sign up."}
        )
