import logging

from celery import shared_task

from api.media_utils import compress_image_to_webp
from .models import PetProfile

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def process_pet_image_task(self, pet_id: str):
    """Compress pet profile image asynchronously and clean up replaced file."""
    try:
        pet = PetProfile.objects.get(id=pet_id)
    except PetProfile.DoesNotExist:
        logger.error("PetProfile %s not found for media processing.", pet_id)
        return

    if not pet.image:
        return

    old_name = pet.image.name
    compressed = compress_image_to_webp(pet.image)
    if not compressed:
        return

    try:
        pet.image.save(compressed.name, compressed, save=False)
        pet.save(update_fields=["image"])

        if old_name and old_name != pet.image.name:
            pet.image.storage.delete(old_name)
    except Exception as exc:
        logger.exception("Failed to process pet image for %s: %s", pet_id, exc)
        raise self.retry(exc=exc)
