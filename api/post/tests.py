from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.core.files.uploadedfile import SimpleUploadedFile

from api.friends.models import Friendship
from .models import Post, PostComment, PostMedia, SavedPost, PrivacyChoices

User = get_user_model()


class PostBaseTestCase(TestCase):
    """Base setup for post tests."""

    def setUp(self):
        self.client = APIClient()

        self.alice = User.objects.create_user(
            email="alice@test.com", username="alice",
            phone="10000001", password="pass",
            is_verified=True,
        )
        self.bob = User.objects.create_user(
            email="bob@test.com", username="bob",
            phone="10000002", password="pass",
            is_verified=True,
        )
        # Profile creation handled by signal

    def make_friends(self, user_a, user_b):
        Friendship.objects.get_or_create(sender=user_a, receiver=user_b)


class PostAPITest(PostBaseTestCase):
    """Tests for Post CRUD and Feed."""

    def test_create_post_text_only(self):
        self.client.force_authenticate(self.alice)
        url = reverse('post-list')
        data = {
            "content_text": "Hello world #test",
            "privacy": "PUBLIC"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Post.objects.count(), 1)
        self.assertEqual(Post.objects.first().hashtags.count(), 1)

    def test_create_post_with_media(self):
        self.client.force_authenticate(self.alice)
        url = reverse('post-list')
        image = SimpleUploadedFile("test.jpg", b"file_content", content_type="image/jpeg")
        data = {
            "content_text": "Post with media",
            "media": [image]
        }
        # Use format='multipart' for file uploads
        response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PostMedia.objects.count(), 1)

    def test_feed_visibility_friends_only(self):
        # Alice creates a public post
        Post.objects.create(author=self.alice, content_text="Public", privacy=PrivacyChoices.PUBLIC)
        
        # Bob (stranger) does NOT see it in Feed (Feed is for friends)
        self.client.force_authenticate(self.bob)
        response = self.client.get(reverse('post-feed'))
        self.assertEqual(len(response.data['results']), 0)

        # Make them friends -> now he sees it
        self.make_friends(self.alice, self.bob)
        response = self.client.get(reverse('post-feed'))
        self.assertEqual(len(response.data['results']), 1)

    def test_guest_can_see_public_post_via_list(self):
        # Alice creates a public post
        Post.objects.create(author=self.alice, content_text="Public", privacy=PrivacyChoices.PUBLIC)
        
        # Bob (stranger) checks Alice's posts via PostService logic (list view)
        self.client.force_authenticate(self.bob)
        # We need a detail or list view that uses get_user_posts
        url = reverse('post-list') # Standard list returns own posts
        # To see others, we usually have a profile posts endpoint.
        # Let's check permissions on individual post
        post = Post.objects.first()
        url = reverse('post-detail', kwargs={'pk': post.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_feed_privacy_friends_only(self):
        # Alice creates a friends-only post
        Post.objects.create(author=self.alice, content_text="Friends Only", privacy=PrivacyChoices.FRIENDS_ONLY)
        
        # Bob (stranger) should NOT see it even if he follows (he needs to be a friend)
        self.client.force_authenticate(self.bob)
        response = self.client.get(reverse('post-feed'))
        self.assertEqual(len(response.data['results']), 0)
        
        # Make them friends
        self.make_friends(self.alice, self.bob)
        response = self.client.get(reverse('post-feed'))
        self.assertEqual(len(response.data['results']), 1)

    def test_soft_delete(self):
        post = Post.objects.create(author=self.alice, content_text="Delete me")
        self.client.force_authenticate(self.alice)
        url = reverse('post-detail', kwargs={'pk': post.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        post.refresh_from_db()
        self.assertTrue(post.is_deleted)


class InteractionAPITest(PostBaseTestCase):
    """Tests for Likes, Comments, and Saves."""

    def setUp(self):
        super().setUp()
        self.post = Post.objects.create(author=self.alice, content_text="Interaction Test")

    def test_toggle_like_restricted_to_author(self):
        # Bob tries to like Alice's post
        self.client.force_authenticate(self.bob)
        url = reverse('post-like', kwargs={'pk': self.post.id})
        
        # Like Attempt (Should fail with 403 per IsAuthorOrReadOnly)
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Alice (Author) can like/react
        self.client.force_authenticate(self.alice)
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_comment_and_reply(self):
        self.client.force_authenticate(self.bob)
        url = reverse('comment-list')
        
        # Comment
        data = {"post": str(self.post.id), "comment_text": "Nice post!"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        comment_id = response.data['id']
        
        # Reply
        data = {
            "post": str(self.post.id),
            "parent_comment": comment_id,
            "comment_text": "I agree!"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        self.post.refresh_from_db()
        self.assertEqual(self.post.comments_count, 2)
        
        parent = PostComment.objects.get(id=comment_id)
        self.assertEqual(parent.replies_count, 1)

    def test_toggle_save_restricted_to_author(self):
        self.client.force_authenticate(self.bob)
        url = reverse('post-save-post', kwargs={'pk': self.post.id})
        
        # Save Attempt (Should fail with 403)
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Alice (Author) can save
        self.client.force_authenticate(self.alice)
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
