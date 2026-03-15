"""
Custom DRF exception handler for production-grade error responses.

Ensures that all errors return clean JSON and never expose 500 stack traces.
"""

import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that converts all exceptions to clean JSON.

    Response format:
        {
            "success": false,
            "message": "Human-readable error message",
            "errors": { ... }  # optional field-level errors
        }
    """
    # Let DRF handle known exceptions first
    response = exception_handler(exc, context)

    if response is not None:
        # DRF handled it — normalize the format
        error_data = {"success": False}

        if isinstance(response.data, dict):
            # Extract 'detail' or field-level errors
            detail = response.data.pop("detail", None)
            if detail:
                error_data["message"] = str(detail)
            elif response.data:
                error_data["message"] = "Validation failed."
                error_data["errors"] = response.data
            else:
                error_data["message"] = "An error occurred."
        elif isinstance(response.data, list):
            error_data["message"] = " ".join(str(item) for item in response.data)
        else:
            error_data["message"] = str(response.data)

        response.data = error_data
        return response

    # DRF didn't handle it — it's an unexpected error
    if isinstance(exc, DjangoValidationError):
        error_data = {
            "success": False,
            "message": "Validation failed.",
            "errors": exc.message_dict
            if hasattr(exc, "message_dict")
            else {"detail": exc.messages},
        }
        return Response(error_data, status=status.HTTP_400_BAD_REQUEST)

    if isinstance(exc, Http404):
        return Response(
            {"success": False, "message": "Resource not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Completely unexpected error — log it, return generic message
    logger.exception("Unhandled exception in %s", context.get("view", "unknown"))
    return Response(
        {
            "success": False,
            "message": "An internal error occurred. Please try again later.",
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
