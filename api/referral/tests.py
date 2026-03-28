from decimal import Decimal
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.users.models import Profile
from .models import ReferralSettings, ReferralTransaction, ReferralWallet, TransactionType

User = get_user_model()

class ReferralSystemTests(APITestCase):
    def setUp(self):
        # Create global settings
        self.settings = ReferralSettings.objects.create(
            referrer_points=Decimal("10.00"),
            referee_points=Decimal("5.00")
        )
        
        # Create User A (Referrer)
        self.user_a = User.objects.create_user(
            email="user_a@example.com",
            password="password123",
            username="usera",
            is_verified=True
        )
        # Profile is created via signal, referral_code is auto-generated
        self.profile_a = self.user_a.profile
        self.referral_code_a = self.profile_a.referral_code

    def test_signup_with_referral_code_awards_points(self):
        """Test that signing up with a referral code awards points to both users."""
        signup_url = reverse("signup")
        data = {
            "email": "user_b@example.com",
            "password": "Password123!",  # Stronger password
            "first_name": "User",
            "last_name": "B",
            "agree_to_terms_and_conditions": True,
            "referred_by_code": self.referral_code_a
        }
        
        response = self.client.post(signup_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify User B exists and has referred_by set to User A
        user_b = User.objects.get(email="user_b@example.com")
        self.assertEqual(user_b.profile.referred_by, self.user_a)
        
        # Verify Wallets and Points
        wallet_a = ReferralWallet.objects.get(user=self.user_a)
        wallet_b = ReferralWallet.objects.get(user=user_b)
        
        self.assertEqual(wallet_a.balance, Decimal("10.00"))  # Referrer points
        self.assertEqual(wallet_b.balance, Decimal("5.00"))   # Referee points
        
        # Verify Transactions
        tx_a = ReferralTransaction.objects.filter(wallet=wallet_a, transaction_type=TransactionType.REFERRAL_COMMISSION).first()
        tx_b = ReferralTransaction.objects.filter(wallet=wallet_b, transaction_type=TransactionType.SIGNUP_BONUS).first()
        
        self.assertIsNotNone(tx_a)
        self.assertIsNotNone(tx_b)
        self.assertEqual(tx_a.amount, Decimal("10.00"))
        self.assertEqual(tx_b.amount, Decimal("5.00"))

    def test_duplicate_point_award_prevention(self):
        """Test that points are not awarded twice for the same user."""
        from .services import award_referral_points
        
        # Signup User B with referral
        user_b = User.objects.create_user(
            email="user_b@example.com", 
            password="Password123!",
            username="userb"
        )
        user_b.profile.referred_by = self.user_a
        user_b.profile.save() # Signal fires here
        
        # Points should be awarded (checked in previous test)
        wallet_a = ReferralWallet.objects.get(user=self.user_a)
        self.assertEqual(wallet_a.balance, Decimal("10.00"))
        
        # Try to award again manually
        award_referral_points(user_b)
        
        # Balance should still be 10, not 20
        wallet_a.refresh_from_db()
        self.assertEqual(wallet_a.balance, Decimal("10.00"))

    def test_referral_stats_api(self):
        """Test the /api/referral/my/ endpoint."""
        self.client.force_authenticate(user=self.user_a)
        url = reverse("referral-my") # Fixed name
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["referral_code"], self.referral_code_a)
        self.assertEqual(float(response.data["balance"]), 0.0)

    def test_dashboard_api(self):
        """Test the /api/referral/dashboard/ endpoint."""
        # Setup: User A refers User B
        user_b = User.objects.create_user(email="b@x.com", username="b", password="Password123!")
        user_b.profile.referred_by = self.user_a
        user_b.profile.save()
        
        self.client.force_authenticate(user=self.user_a)
        url = reverse("referral-dashboard")
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["joined_count"], 1)
        # members is a list directly, not paginated here
        self.assertEqual(len(response.data["members"]), 1)
        self.assertEqual(response.data["members"][0]["email"], "b@x.com")

    def test_transactions_api(self):
        """Test the /api/referral/transactions/ endpoint."""
        # Setup: Award points
        user_b = User.objects.create_user(email="b@x.com", username="b", password="p")
        user_b.profile.referred_by = self.user_a
        user_b.profile.save()
        
        self.client.force_authenticate(user=self.user_a)
        url = reverse("referral-transactions")
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["transaction_type"], TransactionType.REFERRAL_COMMISSION)
