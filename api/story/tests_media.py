import io
import tempfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from api.story.models import Story, StoryMediaTypeChoices
from api.story.tasks import process_story_media_task
from api.users.models import User


def make_test_image(name="story.jpg", size=(1600, 1200)):
    buffer = io.BytesIO()
    image = Image.new("RGB", size, color=(0, 0, 255))
    image.save(buffer, format="JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class StoryMediaCompressionTests(TestCase):
    def test_story_image_is_converted_to_webp(self):
        user = User.objects.create_user(email="story@test.com", username="storyuser")
        story = Story.objects.create(
            author=user,
            media_type=StoryMediaTypeChoices.IMAGE,
            media=make_test_image(),
            expires_at=timezone.now() + timedelta(hours=24),
        )

        # Store original filename for deletion check
        original_filename = story.media.name

        process_story_media_task(str(story.id))
        story.refresh_from_db()

        # Test 1: Compression - file extension changed to .webp
        self.assertTrue(story.media.name.lower().endswith(".webp"),
                       f"Image should be .webp, got {story.media.name}")

        # Test 2: Save - filename actually changed in DB
        self.assertNotEqual(original_filename, story.media.name,
                           "Filename should have changed after compression")

        # Test 3: File exists in storage
        self.assertTrue(default_storage.exists(story.media.name),
                       f"Compressed file {story.media.name} should exist in storage")

        # Test 4: Old file deleted from storage
        self.assertFalse(default_storage.exists(original_filename),
                        f"Original file {original_filename} should be deleted after compression")


