from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from decimal import Decimal

from .models import VerificationConfig

User = get_user_model()

class AppVerifyTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@test.com", 
            password="testpassword",
            phone="+1234567890"
        )
        self.config = VerificationConfig.get_instance()

    def test_config_view(self):
        """Test public configuration endpoint"""
        url = reverse('verification-config')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(response.data['verification_price']), str(self.config.verification_price))

    def test_status_view_unauthenticated(self):
        """Test status endpoint blocks unauthorized access"""
        url = reverse('verification-status')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_status_view_authenticated(self):
        """Test status endpoint accurately reports verification info"""
        self.client.force_authenticate(user=self.user)
        url = reverse('verification-status')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['is_app_verified'], False)
        self.assertEqual(response.data['is_identity_verified'], False)
        self.assertEqual(response.data['persona_status'], 'pending')

    def test_revenuecat_webhook_updates_user(self):
        """Test RevenueCat correctly updates user payment status"""
        url = reverse('revenuecat-webhook')
        payload = {
            "event": {
                "type": "INITIAL_PURCHASE",
                "app_user_id": str(self.user.id)
            }
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_app_verified)

    def test_persona_init_requires_payment(self):
        """Test Persona init checks payment firewall"""
        self.client.force_authenticate(user=self.user)
        url = reverse('persona-init')
        response = self.client.post(url)
        # 402 Payment Required because we haven't paid yet
        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)

    def test_persona_init_blocks_exceeding_attempts(self):
        """Test Persona config strictly limits hacking attempts"""
        # Simulate payment success
        self.user.is_app_verified = True
        
        # Max out attempts artificially
        self.user.persona_verification_attempts = 3
        self.user.save()
        
        self.client.force_authenticate(user=self.user)
        url = reverse('persona-init')
        response = self.client.post(url)
        
        # 403 Forbidden because we hit the logic limit
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
