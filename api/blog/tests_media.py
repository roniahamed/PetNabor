import io
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from PIL import Image

from api.blog.models import Blog, BlogComment
from api.blog.tasks import process_blog_comment_media_task
from api.users.models import User


def make_test_image(name="blog_comment.jpg", size=(1000, 700)):
    buffer = io.BytesIO()
    image = Image.new("RGB", size, color=(40, 120, 40))
    image.save(buffer, format="JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class BlogCommentMediaCompressionTests(TestCase):
    def test_blog_comment_image_is_converted_to_webp(self):
        user = User.objects.create_user(email="blog@test.com", username="bloguser")
        blog = Blog.objects.create(author=user, title="T", content_body="Content")

        comment = BlogComment.objects.create(
            blog=blog,
            user=user,
            comment_text="Nice",
            media_file=make_test_image(),
        )

        # Store original filename for deletion check
        original_filename = comment.media_file.name

        process_blog_comment_media_task(str(comment.id))
        comment.refresh_from_db()

        # Test 1: Compression - file extension changed to .webp
        self.assertTrue(comment.media_file.name.lower().endswith(".webp"),
                       f"Image should be .webp, got {comment.media_file.name}")

        # Test 2: Save - filename actually changed in DB
        self.assertNotEqual(original_filename, comment.media_file.name,
                           "Filename should have changed after compression")

        # Test 3: File exists in storage
        self.assertTrue(default_storage.exists(comment.media_file.name),
                       f"Compressed file {comment.media_file.name} should exist in storage")

        # Test 4: Old file deleted from storage
        self.assertFalse(default_storage.exists(original_filename),
                        f"Original file {original_filename} should be deleted after compression")


