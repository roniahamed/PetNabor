import uuid
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .models import Report, ReportTargetTypeChoices

User = get_user_model()


class ReportAPITest(TestCase):
    """Tests for Report submission and management."""

    def setUp(self):
        self.client = APIClient()

        self.alice = User.objects.create_user(
            email="alice@test.com", username="alice",
            phone="10000001", password="pass",
            is_verified=True,
        )
        self.staff_user = User.objects.create_user(
            email="staff@test.com", username="staff",
            phone="10000002", password="pass",
            is_verified=True, is_staff=True,
        )
        # Profile creation handled by signal

        self.report_list_url = reverse('report-list')

    def test_submit_report(self):
        self.client.force_authenticate(self.alice)
        target_id = uuid.uuid4()
        data = {
            "target_type": ReportTargetTypeChoices.POST,
            "target_id": str(target_id),
            "reason": "Harassment",
            "description": "User is being mean."
        }
        response = self.client.post(self.report_list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Report.objects.count(), 1)
        self.assertEqual(Report.objects.first().reporter, self.alice)

    def test_multiple_reports_allowed(self):
        self.client.force_authenticate(self.alice)
        target_id = uuid.uuid4()
        data = {
            "target_type": ReportTargetTypeChoices.POST,
            "target_id": str(target_id),
            "reason": "Spam"
        }
        # First submission
        self.client.post(self.report_list_url, data, format='json')
        # Second submission (now allowed)
        response = self.client.post(self.report_list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Report.objects.count(), 2)

    def test_user_can_only_see_own_reports(self):
        # Alice's report
        Report.objects.create(
            reporter=self.alice, target_type=ReportTargetTypeChoices.POST,
            target_id=uuid.uuid4(), reason="R1"
        )
        # Another user's report
        bob = User.objects.create_user(email="bob@test.com", username="bob", phone="10000003", password="pass")
        # Profile creation handled by signal
        Report.objects.create(
            reporter=bob, target_type=ReportTargetTypeChoices.POST,
            target_id=uuid.uuid4(), reason="R2"
        )

        self.client.force_authenticate(self.alice)
        response = self.client.get(self.report_list_url)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['reason'], "R1")

    def test_staff_can_see_all_reports(self):
        Report.objects.create(
            reporter=self.alice, target_type=ReportTargetTypeChoices.POST,
            target_id=uuid.uuid4(), reason="R1"
        )
        self.client.force_authenticate(self.staff_user)
        response = self.client.get(self.report_list_url)
        self.assertEqual(len(response.data['results']), 1)

    def test_admin_resolve_report(self):
        report = Report.objects.create(
            reporter=self.alice, target_type=ReportTargetTypeChoices.POST,
            target_id=uuid.uuid4(), reason="R1"
        )
        self.client.force_authenticate(self.staff_user)
        url = reverse('report-resolve', kwargs={'pk': report.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        report.refresh_from_db()
        self.assertTrue(report.is_resolved)
