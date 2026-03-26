from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from .models import Meeting, MeetingFeedback
from api.friends.models import Friendship

User = get_user_model()

class MeetingAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user1 = User.objects.create_user(
            username='user1', email='user1@example.com', password='password123',
            first_name='User', last_name='One'
        )
        self.user2 = User.objects.create_user(
            username='user2', email='user2@example.com', password='password123',
            first_name='User', last_name='Two'
        )
        self.user3 = User.objects.create_user(
            username='user3', email='user3@example.com', password='password123',
            first_name='User', last_name='Three'
        )

        # Make user1 and user2 friends
        Friendship.objects.create(sender=self.user1, receiver=self.user2)

    def test_create_meeting_with_friend(self):
        self.client.force_authenticate(user=self.user1)
        data = {
            'receiver_id': str(self.user2.id),
            'visitor_name': 'Test Visitor',
            'visitor_phone': '1234567890',
            'visit_date': '2030-01-01',
            'visit_time': '10:00:00',
            'reason': 'Meet & Greet',
            'address_street': '123 Test St',
            'city': 'Test City',
            'state': 'Test State',
            'zipcode': '12345',
            'message': 'Hello friend'
        }
        response = self.client.post('/api/meetings/requests/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Meeting.objects.count(), 1)
        meeting = Meeting.objects.first()
        self.assertEqual(meeting.status, 'PENDING')

    def test_create_meeting_with_non_friend(self):
        self.client.force_authenticate(user=self.user1)
        data = {
            'receiver_id': str(self.user3.id),
            'visitor_name': 'Test Visitor',
            'visitor_phone': '1234567890',
            'visit_date': '2030-01-01',
            'visit_time': '10:00:00',
            'reason': 'Meet & Greet',
            'address_street': '123 Test St',
            'city': 'Test City',
            'state': 'Test State',
            'zipcode': '12345',
            'message': 'Hello friend'
        }
        response = self.client.post('/api/meetings/requests/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Meeting.objects.count(), 0)

    def test_accept_meeting(self):
        meeting = Meeting.objects.create(
            sender=self.user1, receiver=self.user2,
            visitor_name='Test Visitor', visitor_phone='1234567890',
            visit_date='2030-01-01', visit_time='10:00:00',
            reason='Meet & Greet', address_street='123 Test St',
            city='Test City', state='Test State', zipcode='12345'
        )
        
        self.client.force_authenticate(user=self.user2)
        response = self.client.post(f'/api/meetings/requests/{meeting.id}/accept/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        meeting.refresh_from_db()
        self.assertEqual(meeting.status, 'ACCEPTED')

    def test_complete_meeting(self):
        meeting = Meeting.objects.create(
            sender=self.user1, receiver=self.user2,
            visitor_name='Test Visitor', visitor_phone='1234567890',
            visit_date='2030-01-01', visit_time='10:00:00',
            reason='Meet & Greet', address_street='123 Test St',
            city='Test City', state='Test State', zipcode='12345',
            status='ACCEPTED'
        )
        
        self.client.force_authenticate(user=self.user1)
        response = self.client.post(f'/api/meetings/requests/{meeting.id}/complete/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        meeting.refresh_from_db()
        self.assertEqual(meeting.status, 'COMPLETED')

    def test_give_feedback(self):
        meeting = Meeting.objects.create(
            sender=self.user1, receiver=self.user2,
            visitor_name='Test Visitor', visitor_phone='1234567890',
            visit_date='2020-01-01', visit_time='10:00:00',
            reason='Meet & Greet', address_street='123 Test St',
            city='Test City', state='Test State', zipcode='12345',
            status='COMPLETED'
        )

        self.client.force_authenticate(user=self.user1)
        data = {
            'meeting': str(meeting.id),
            'reviewee': str(self.user2.id),
            'rating': 5,
            'feedback_text': 'Great meeting!'
        }
        response = self.client.post('/api/meetings/feedback/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(MeetingFeedback.objects.count(), 1)
