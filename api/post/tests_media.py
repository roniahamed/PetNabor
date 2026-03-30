import io
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from PIL import Image

from api.post.models import Post, PostComment
from api.post.tasks import process_post_comment_media_task
from api.users.models import User


def make_test_image(name="comment.jpg", size=(1200, 900)):
    buffer = io.BytesIO()
    image = Image.new("RGB", size, color=(120, 40, 40))
    image.save(buffer, format="JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class PostCommentMediaCompressionTests(TestCase):
    def test_comment_image_is_converted_to_webp(self):
        user = User.objects.create_user(email="post@test.com", username="postuser")
        post = Post.objects.create(author=user, content_text="Hello")

        comment = PostComment.objects.create(
            post=post,
            user=user,
            media_file=make_test_image(),
            comment_text="With image",
        )

        # Store original filename for deletion check
        original_filename = comment.media_file.name

        process_post_comment_media_task(str(comment.id))
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


