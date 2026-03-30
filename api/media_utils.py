import os
from io import BytesIO
from typing import Optional

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, UnidentifiedImageError


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff"}


def _get_max_dim() -> tuple[int, int]:
    return tuple(getattr(settings, "POST_IMAGE_MAX_DIM", (1920, 1080)))


def _get_quality() -> int:
    return int(getattr(settings, "POST_IMAGE_QUALITY", 85))


def should_process_media_field(instance, field_name: str, update_fields=None) -> bool:
    """Return True only when a media field is present and changed on this save."""
    if update_fields is not None and field_name not in set(update_fields):
        return False

    media_field = getattr(instance, field_name, None)
    if not media_field:
        return False

    current_name = getattr(media_field, "name", None)
    if not current_name:
        return False

    if instance._state.adding:
        return True

    if not instance.pk:
        return True

    previous_name = (
        type(instance)
        .objects.filter(pk=instance.pk)
        .values_list(field_name, flat=True)
        .first()
    )
    return current_name != previous_name


def compress_image_to_webp(uploaded_file, max_dim: Optional[tuple[int, int]] = None, quality: Optional[int] = None):
    """
    Convert uploaded image files to resized WebP.
    Returns ContentFile for image inputs, otherwise None.
    """
    if not uploaded_file:
        return None

    original_name = os.path.basename(getattr(uploaded_file, "name", "upload"))
    _, ext = os.path.splitext(original_name)

    content_type = getattr(uploaded_file, "content_type", "") or ""
    if not content_type.startswith("image/") and ext.lower() not in IMAGE_EXTENSIONS:
        return None

    max_dim = max_dim or _get_max_dim()
    quality = quality if quality is not None else _get_quality()

    try:
        if hasattr(uploaded_file, "open"):
            uploaded_file.open("rb")
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)

        img = Image.open(uploaded_file)
        img.verify()

        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)

        img = Image.open(uploaded_file)
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        elif img.mode != "RGB":
            img = img.convert("RGB")

        resized = img.copy()
        resized.thumbnail(max_dim, Image.Resampling.LANCZOS)

        output = BytesIO()
        resized.save(output, format="WEBP", quality=quality, method=6)
        output.seek(0)

        base_name = os.path.splitext(original_name)[0]
        return ContentFile(output.read(), name=f"{base_name}.webp")
    except (UnidentifiedImageError, OSError, ValueError):
        return None
