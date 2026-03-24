from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from django.urls import reverse
from blog.models import Blog, BlogCategory, BlogComment, BlogLike

User = get_user_model()

class BlogAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password', email='test@test.com')
        self.category = BlogCategory.objects.create(name='Technology')
        self.client.force_authenticate(user=self.user)
        self.blog = Blog.objects.create(
            author=self.user,
            category=self.category,
            title='My first blog',
            content_body='Content of the blog.',
            is_published=True
        )

    def test_list_blogs(self):
        url = reverse('blog-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Paginated check
        results = response.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], 'My first blog')

    def test_create_blog(self):
        url = reverse('blog-list')
        data = {
            'title': 'Another blog',
            'content_body': 'Another content',
            'category_id': self.category.id,
            'is_published': True
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'Another blog')
        self.assertEqual(Blog.objects.count(), 2)

    def test_like_blog(self):
        url = reverse('blog-like', kwargs={'slug': self.blog.slug})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_liked'])
        self.assertEqual(response.data['likes_count'], 1)
        
        # Unlike
        response = self.client.post(url)
        self.assertFalse(response.data['is_liked'])
        self.assertEqual(response.data['likes_count'], 0)

    def test_blog_comments(self):
        url = reverse('blog-comments', kwargs={'slug': self.blog.slug})
        data = {'comment_text': 'Great post!'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(BlogComment.objects.count(), 1)
        
        # Test Get Comments
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['comment_text'], 'Great post!')
