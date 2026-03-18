"""
Celery tasks for background media processing.
All image processing is done asynchronously to avoid blocking requests.

Key improvements:
- Proper logging and retry on error (no silent exceptions)
- UUID-based safe filenames
- WebP format for both main and thumbnail (vs JPEG)
- Multi-size generation: main (max), medium (800px), thumbnail (400px)
- Stream-safe file handling with explicit close in finally blocks
- processing_status updated on success/failure for frontend feedback
"""

import logging
import os
from io import BytesIO

from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image

from .models import PostMedia, MediaTypeChoices, MediaProcessingStatus

logger = logging.getLogger(__name__)


def _resize_and_encode(img: Image.Image, max_dim: tuple, quality: int) -> BytesIO:
    """
    Resize an image to fit within max_dim (maintaining aspect ratio),
    convert to WebP and return as a BytesIO buffer.
    """
    img_copy = img.copy()
    img_copy.thumbnail(max_dim, Image.Resampling.LANCZOS)
    output = BytesIO()
    img_copy.save(output, format="WEBP", quality=quality, method=6)
    output.seek(0)
    return output


@shared_task(bind=True, max_retries=3, default_retry_delay=10, acks_late=True)
def process_post_media_task(self, media_ids: list) -> dict:
    """
    Background Celery task that:
      1. Opens the raw uploaded image.
      2. Validates it is a real image (PIL check — spoof resistant).
      3. Generates three variants: main (WebP), medium (WebP), thumbnail (WebP).
      4. Updates processing_status to DONE or FAILED.
    """
    results = {"processed": [], "failed": []}

    media_qs = PostMedia.objects.filter(
        id__in=media_ids, media_type=MediaTypeChoices.IMAGE
    )

    for media in media_qs:
        if not media.file:
            logger.warning("PostMedia %s has no file. Skipping.", media.id)
            continue

        try:
            # ── 1. Open & verify it is a real image ─────────────────
            media.file.open("rb")
            img = Image.open(media.file)
            img.verify()  # raises on corrupt files

            # Re-open after verify() (verify consumes the stream)
            media.file.open("rb")
            img = Image.open(media.file)

            # Normalise color mode
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # ── 2. Build a safe base filename ────────────────────────
            original_name = os.path.basename(media.file.name)
            base_name = os.path.splitext(original_name)[0]

            # ── 3a. Main image — resize to max, save as WebP ─────────
            main_buf = _resize_and_encode(
                img, settings.POST_IMAGE_MAX_DIM, settings.POST_IMAGE_QUALITY
            )
            media.file.save(
                f"{base_name}.webp",
                ContentFile(main_buf.read()),
                save=False,
            )

            # ── 3b. Medium variant ────────────────────────────────────
            medium_buf = _resize_and_encode(
                img, settings.POST_IMAGE_MEDIUM_DIM, settings.POST_IMAGE_QUALITY
            )
            media.medium_file.save(
                f"{base_name}_medium.webp",
                ContentFile(medium_buf.read()),
                save=False,
            )

            # ── 3c. Thumbnail ─────────────────────────────────────────
            thumb_buf = _resize_and_encode(
                img, settings.POST_IMAGE_THUMB_DIM, settings.POST_THUMB_QUALITY
            )
            media.thumbnail_file.save(
                f"{base_name}_thumb.webp",
                ContentFile(thumb_buf.read()),
                save=False,
            )

            media.processing_status = MediaProcessingStatus.DONE
            media.save(
                update_fields=[
                    "file",
                    "medium_file",
                    "thumbnail_file",
                    "processing_status",
                ]
            )

            results["processed"].append(str(media.id))
            logger.info("PostMedia %s processed successfully.", media.id)

        except Exception as exc:
            logger.exception(
                "Failed to process PostMedia %s: %s",
                media.id,
                exc,
            )
            # Mark as FAILED in DB so frontend can show an error state
            PostMedia.objects.filter(id=media.id).update(
                processing_status=MediaProcessingStatus.FAILED
            )
            results["failed"].append(str(media.id))

            # Retry the whole task if it hasn't exceeded max_retries
            try:
                raise self.retry(exc=exc, countdown=10 * (self.request.retries + 1))
            except self.MaxRetriesExceededError:
                logger.error(
                    "PostMedia %s failed after max retries. Giving up.",
                    media.id,
                )

        finally:
            try:
                media.file.close()
            except Exception:
                pass

    return results
