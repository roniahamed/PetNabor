import io
import tempfile

from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from PIL import Image

from api.users.models import User
from api.users.tasks import process_profile_media_task


def make_test_image(name="profile.jpg", size=(1200, 800)):
    buffer = io.BytesIO()
    image = Image.new("RGB", size, color=(255, 0, 0))
    image.save(buffer, format="JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class ProfileMediaCompressionTests(TestCase):
    def test_profile_picture_is_converted_to_webp(self):
        user = User.objects.create_user(email="profile@test.com", username="profileuser")
        profile = user.profile
        profile.profile_picture = make_test_image()
        profile.save(update_fields=["profile_picture"])

        # Store original filename for deletion check
        original_filename = profile.profile_picture.name

        process_profile_media_task(str(profile.id), "profile_picture")
        profile.refresh_from_db()

        # Test 1: Compression - file extension changed to .webp
        self.assertTrue(profile.profile_picture.name.lower().endswith(".webp"),
                       f"Image should be .webp, got {profile.profile_picture.name}")

        # Test 2: Save - filename actually changed in DB
        self.assertNotEqual(original_filename, profile.profile_picture.name,
                           "Filename should have changed after compression")

        # Test 3: File exists in storage
        self.assertTrue(default_storage.exists(profile.profile_picture.name),
                       f"Compressed file {profile.profile_picture.name} should exist in storage")

        # Test 4: Old file deleted from storage
        self.assertFalse(default_storage.exists(original_filename),
                        f"Original file {original_filename} should be deleted after compression")


