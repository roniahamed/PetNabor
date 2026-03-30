import io
import tempfile
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from PIL import Image

from api.pet.models import PetProfile
from api.pet.tasks import process_pet_image_task
from api.users.models import User


def make_test_image(name="pet.jpg", size=(1400, 900)):
    buffer = io.BytesIO()
    image = Image.new("RGB", size, color=(0, 255, 0))
    image.save(buffer, format="JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class PetMediaCompressionTests(TestCase):
    def test_pet_image_is_converted_to_webp(self):
        user = User.objects.create_user(email="pet@test.com", username="petowner")
        pet = PetProfile.objects.create(
            user=user,
            pet_name="Buddy",
            pet_type="Dog",
            size="Medium",
            weight="12.5",
            date_of_birth=date(2020, 1, 1),
            vaccination_status="Done",
            image=make_test_image(),
        )

        # Store original filename for deletion check
        original_filename = pet.image.name

        process_pet_image_task(str(pet.id))
        pet.refresh_from_db()

        # Test 1: Compression - file extension changed to .webp
        self.assertTrue(pet.image.name.lower().endswith(".webp"), 
                       f"Image should be .webp, got {pet.image.name}")

        # Test 2: Save - filename actually changed in DB
        self.assertNotEqual(original_filename, pet.image.name,
                           "Filename should have changed after compression")

        # Test 3: File exists in storage
        self.assertTrue(default_storage.exists(pet.image.name),
                       f"Compressed file {pet.image.name} should exist in storage")

        # Test 4: Old file deleted from storage
        self.assertFalse(default_storage.exists(original_filename),
                        f"Original file {original_filename} should be deleted after compression")



    def test_non_image_document_remains_unchanged(self):
        user = User.objects.create_user(email="doc@test.com", username="docowner")
        doc = SimpleUploadedFile("vaccination.pdf", b"pdf-content", content_type="application/pdf")

        pet = PetProfile.objects.create(
            user=user,
            pet_name="Milo",
            pet_type="Cat",
            size="Small",
            weight="4.3",
            date_of_birth=date(2021, 1, 1),
            vaccination_status="Done",
            vaccination_document=doc,
        )

        self.assertTrue(pet.vaccination_document.name.lower().endswith(".pdf"))
