from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.gis.geos import Point

from .models import FriendRequest, Friendship, UserBlock
from api.users.models import Profile, UserTypes

User = get_user_model()

class FriendsAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        
        # Create users
        self.user1 = User.objects.create_user(
            email="user1@example.com", 
            username="user1",
            phone="111111111", 
            password="testpassword",
            first_name="User", 
            last_name="One",
            user_type=UserTypes.PATPAL
        )
        self.user2 = User.objects.create_user(
            email="user2@example.com", 
            username="user2",
            phone="222222222", 
            password="testpassword",
            first_name="User", 
            last_name="Two",
            user_type=UserTypes.PATPAL
        )
        self.user3 = User.objects.create_user(
            email="user3@example.com", 
            username="user3",
            phone="333333333", 
            password="testpassword",
            first_name="User", 
            last_name="Three",
            user_type=UserTypes.PATNABOR
        )
        self.user4 = User.objects.create_user(
            email="user4@example.com", 
            username="user4",
            phone="444444444", 
            password="testpassword",
            first_name="User", 
            last_name="Four",
            user_type=UserTypes.PATPAL
        )
        
        for user in [self.user1, self.user2, self.user3, self.user4]:
            Profile.objects.update_or_create(
                user=user, 
                defaults={'location_point': Point(0.0, 0.0)}
            )
        
        # Assign cities for testing address filters
        self.user1.profile.city = "Dhaka"
        self.user1.profile.save()
        self.user2.profile.city = "Dhaka"
        self.user2.profile.save()
        self.user3.profile.city = "Chittagong"
        self.user3.profile.save()
        self.user4.profile.city = "Sylhet"
        self.user4.profile.save()

    def test_send_friend_request(self):
        self.client.force_authenticate(user=self.user1)
        url = reverse('friend-requests-list')
        data = {'receiver_id': str(self.user2.id)}
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(FriendRequest.objects.count(), 1)
        
    def test_send_friend_request_to_self(self):
        self.client.force_authenticate(user=self.user1)
        url = reverse('friend-requests-list')
        data = {'receiver_id': str(self.user1.id)}
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_accept_friend_request(self):
        req = FriendRequest.objects.create(sender=self.user1, receiver=self.user2, status='pending')
        
        self.client.force_authenticate(user=self.user2)
        url = reverse('friend-requests-accept', kwargs={'pk': req.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        req.refresh_from_db()
        self.assertEqual(req.status, 'accepted')
        self.assertTrue(Friendship.objects.filter(user1=self.user1, user2=self.user2).exists() or Friendship.objects.filter(user1=self.user2, user2=self.user1).exists())

    def test_reject_friend_request(self):
        req = FriendRequest.objects.create(sender=self.user1, receiver=self.user2, status='pending')
        
        self.client.force_authenticate(user=self.user2)
        url = reverse('friend-requests-reject', kwargs={'pk': req.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(FriendRequest.objects.filter(id=req.id).exists())
        
    def test_cancel_friend_request(self):
        req = FriendRequest.objects.create(sender=self.user1, receiver=self.user2, status='pending')
        
        self.client.force_authenticate(user=self.user1)
        url = reverse('friend-requests-cancel', kwargs={'pk': req.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(FriendRequest.objects.filter(id=req.id).exists())

    def test_block_user(self):
        self.client.force_authenticate(user=self.user1)
        url = reverse('block-user')
        data = {'user_id': str(self.user2.id)}
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(UserBlock.objects.filter(blocker=self.user1, blocked_user=self.user2).exists())
        
        self.client.force_authenticate(user=self.user2)
        req_url = reverse('friend-requests-list')
        req_data = {'receiver_id': str(self.user1.id)}
        req_response = self.client.post(req_url, req_data, format='json')
        self.assertEqual(req_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unblock_user(self):
        UserBlock.objects.create(blocker=self.user1, blocked_user=self.user2)
        self.client.force_authenticate(user=self.user1)
        
        url = reverse('block-user')
        data = {'user_id': str(self.user2.id)}
        response = self.client.delete(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(UserBlock.objects.filter(blocker=self.user1, blocked_user=self.user2).exists())

    def test_get_blocks(self):
        UserBlock.objects.create(blocker=self.user1, blocked_user=self.user2)
        self.client.force_authenticate(user=self.user1)
        url = reverse('block-user')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_remove_friend(self):
        Friendship.objects.create(user1=self.user1, user2=self.user2)
        self.client.force_authenticate(user=self.user1)
        
        url = reverse('remove-friend')
        data = {'user_id': str(self.user2.id)}
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Friendship.objects.filter(user1=self.user1, user2=self.user2).exists())

    def test_friend_list(self):
        Friendship.objects.create(user1=self.user1, user2=self.user2)
        Friendship.objects.create(user1=self.user1, user2=self.user3)
        
        self.client.force_authenticate(user=self.user1)
        url = reverse('list-friends')
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        
        response_pals = self.client.get(url + '?type=petpals')
        self.assertEqual(len(response_pals.data['results']), 1)
        
        response_nabors = self.client.get(url + '?type=petnabors')
        self.assertEqual(len(response_nabors.data['results']), 1)

    def test_nearby_users_search(self):
        self.client.force_authenticate(user=self.user1)
        url = reverse('search-users')
        
        response = self.client.get(url + '?type=patpal&radius=10')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Now includes self, so should see user1, user2 and user4 (all PATPAL)
        self.assertEqual(len(response.data['results']), 3)

    def test_advanced_search_filters(self):
        # Establish friendships first: user1 is friends with user2 and user3
        Friendship.objects.create(user1=self.user1, user2=self.user2)
        Friendship.objects.create(user1=self.user1, user2=self.user3)
        
        self.client.force_authenticate(user=self.user1)
        url = reverse('search-users')
        
        # 1. Test "All" users (no type specified)
        # Should see user2(patpal), user3(patnabor), user4(patpal)
        # include_friends=true by default. Now includes self.
        response_all = self.client.get(url + '?radius=10')
        self.assertEqual(response_all.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response_all.data['results']), 4) 

        # 2. Test explicit friend exclusion
        response_no_friends = self.client.get(url + '?radius=10&include_friends=false')
        # Only user4 is not a friend. user2 and user3 are friends.
        # user1 (self) is also not a "friend" of self, so shows up.
        self.assertEqual(len(response_no_friends.data['results']), 2)
        usernames = [u['username'] for u in response_no_friends.data['results']]
        self.assertIn('user4', usernames)
        self.assertIn('user1', usernames)

        # 3. Test specific type with friends
        response_nabors = self.client.get(url + '?type=patnabor&radius=10')
        # user3 is patnabor and a friend. Should be included.
        self.assertEqual(len(response_nabors.data['results']), 1)
        self.assertEqual(response_nabors.data['results'][0]['username'], 'user3')

    def test_global_search(self):
        self.client.force_authenticate(user=self.user1)
        url = reverse('search-users')
        
        # 1. Global search (radius=all)
        # Should see all users: user1, user2, user3, user4
        response_all = self.client.get(url + '?radius=all')
        self.assertEqual(len(response_all.data['results']), 4)

    def test_city_search(self):
        self.client.force_authenticate(user=self.user1)
        url = reverse('search-users')
        
        # 2. Search by city (radius=all to ignore distance)
        response_dhaka = self.client.get(url + '?radius=all&city=Dhaka')
        self.assertEqual(len(response_dhaka.data['results']), 2) # user1 and user2 are in Dhaka
        usernames = [u['username'] for u in response_dhaka.data['results']]
        self.assertIn('user1', usernames)
        self.assertIn('user2', usernames)
        
        response_sylhet = self.client.get(url + '?radius=all&city=Sylhet')
        self.assertEqual(len(response_sylhet.data['results']), 1)
        self.assertEqual(response_sylhet.data['results'][0]['username'], 'user4')

    @patch('api.friends.services.send_notification')
    def test_friend_request_notifications(self, mock_notify):
        from api.notifications.models import NotificationTypes
        self.client.force_authenticate(user=self.user1)
        url = reverse('friend-requests-list')
        data = {'receiver_id': str(self.user2.id)}
        self.client.post(url, data, format='json')
        
        # Check if notification was sent to user2
        self.assertEqual(mock_notify.call_count, 1)
        mock_notify.assert_called_with(
            user_id=self.user2.id,
            title="New Friend Request",
            body="user1 sent you a friend request.",
            notification_type=NotificationTypes.FRIEND_REQUEST
        )

    @patch('api.friends.services.send_notification')
    def test_accept_friend_request_notification(self, mock_notify):
        from api.notifications.models import NotificationTypes
        req = FriendRequest.objects.create(sender=self.user1, receiver=self.user2, status='pending')
        
        self.client.force_authenticate(user=self.user2)
        url = reverse('friend-requests-accept', kwargs={'pk': req.id})
        self.client.post(url)
        
        # In accept_friend_request, sender gets notified
        self.assertEqual(mock_notify.call_count, 1)
        mock_notify.assert_called_with(
            user_id=self.user1.id,
            title="Friend Request Accepted",
            body="user2 accepted your friend request.",
            notification_type=NotificationTypes.FRIEND_ACCEPT
        )

    def test_public_user_detail(self):
        self.client.force_authenticate(user=self.user1)
        url = reverse('user-detail', kwargs={'user_id': self.user3.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'user3')
        # Sensitive data should be missing
        self.assertNotIn('email', response.data)
        self.assertNotIn('phone', response.data)
        # Friendship status should be correctly reported
        self.assertEqual(response.data['friendship_status'], 'none')

    def test_public_user_detail_blocked(self):
        # user2 blocks user1
        UserBlock.objects.create(blocker=self.user2, blocked_user=self.user1)
        
        self.client.force_authenticate(user=self.user1)
        url = reverse('user-detail', kwargs={'user_id': self.user2.id})
        response = self.client.get(url)
        
        # Should be 404 for security/privacy (obfuscating block)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
