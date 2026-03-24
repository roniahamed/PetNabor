import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from django.urls import reverse

User = get_user_model()
alice, _ = User.objects.get_or_create(email="alice_test@test.com", username="alice_test", phone="0001")

client = APIClient()
client.force_authenticate(alice)
url = reverse("story-list")
try:
    response = client.post(url, {"media_type": "TEXT", "text_content": "Hello", "privacy": "PUBLIC"}, format="json")
    print("STATUS CODE:", response.status_code)
    print("RESPONSE:", response.content)
except Exception as e:
    import traceback
    traceback.print_exc()
