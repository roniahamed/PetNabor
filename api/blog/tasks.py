import os
from io import BytesIO
from PIL import Image

from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import F
import logging
from api.media_utils import compress_image_to_webp
from .models import Blog, BlogComment, BlogViewTracker

logger = logging.getLogger(__name__)

@shared_task(name='blog.track_view_async')
def track_view_async(blog_id, ip_address, user_id=None):
    """
    Celery task to asynchronously track views and increment denormalized counters.
    Prevents database locks during high traffic.
    """
    if not ip_address:
        return
        
    try:
        view_exists_query = BlogViewTracker.objects.filter(blog_id=blog_id)
        if user_id:
            view_exists_query = view_exists_query.filter(user_id=user_id)
        else:
            view_exists_query = view_exists_query.filter(ip_address=ip_address)

        if not view_exists_query.exists():
            with transaction.atomic():
                BlogViewTracker.objects.create(
                    blog_id=blog_id, 
                    ip_address=ip_address, 
                    user_id=user_id
                )
                Blog.objects.filter(id=blog_id).update(views_count=F('views_count') + 1)
    except Exception:
        logger.error(f"Failed to track blog view async for {blog_id}", exc_info=True)


def _resize_and_encode(img: Image.Image, max_dim: tuple, quality: int) -> BytesIO:
    """Resize an image maintaining aspect ratio and convert to WebP."""
    img_copy = img.copy()
    img_copy.thumbnail(max_dim, Image.Resampling.LANCZOS)
    output = BytesIO()
    img_copy.save(output, format="WEBP", quality=quality, method=6)
    output.seek(0)
    return output


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def process_blog_cover_task(self, blog_id: str):
    """
    Background task to validate, resize, and convert blog cover to WebP format.
    """
    try:
        blog = Blog.objects.get(id=blog_id)
        if not blog.cover_image:
            return "No cover image found."

        # Open image safely
        blog.cover_image.open("rb")
        img = Image.open(blog.cover_image)
        img.verify()
        
        # Re-open after verify
        blog.cover_image.open("rb")
        img = Image.open(blog.cover_image)

        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Create webp
        original_name = os.path.basename(blog.cover_image.name)
        base_name = os.path.splitext(original_name)[0]
        
        # We reuse the global POST_IMAGE_MAX_DIM/QUALITY, defaulting if missing
        max_dim = getattr(settings, 'POST_IMAGE_MAX_DIM', (1920, 1080))
        quality = getattr(settings, 'POST_IMAGE_QUALITY', 85)
        
        webp_buf = _resize_and_encode(img, max_dim, quality)
        
        # Save explicitly deleting the old format safely
        new_filename = f"{base_name}.webp"
        
        # We can update the field directly and save
        old_file = blog.cover_image
        blog.cover_image.save(new_filename, ContentFile(webp_buf.read()), save=False)
        blog.save(update_fields=['cover_image'])
        
        # Cleanup old if needed, avoiding deleting if they match somehow
        if old_file and old_file.name != blog.cover_image.name:
            if os.path.isfile(old_file.path):
                os.remove(old_file.path)

        return f"Processed cover for blog {blog_id}"

    except Blog.DoesNotExist:
        logger.error(f"Blog {blog_id} not found for media processing.")
    except Exception as exc:
        logger.exception(f"Failed to process cover for blog {blog_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def process_blog_comment_media_task(self, comment_id: str):
    """Compress blog comment media asynchronously and remove replaced old file."""
    try:
        comment = BlogComment.objects.get(id=comment_id)
    except BlogComment.DoesNotExist:
        logger.error("BlogComment %s not found for media processing.", comment_id)
        return

    if not comment.media_file:
        return

    old_name = comment.media_file.name
    compressed = compress_image_to_webp(comment.media_file)
    if not compressed:
        return

    try:
        comment.media_file.save(compressed.name, compressed, save=False)
        comment.save(update_fields=["media_file"])

        if old_name and old_name != comment.media_file.name:
            comment.media_file.storage.delete(old_name)
    except Exception as exc:
        logger.exception("Failed to process blog comment media for %s: %s", comment_id, exc)
        raise self.retry(exc=exc)
