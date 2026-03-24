import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from api.users.models import User
from rest_framework.test import APIClient

user = User.objects.create(email="testpatch@example.com", first_name="Old", last_name="Name")
client = APIClient()
client.force_authenticate(user=user)

response = client.patch('/api/users/user/', {"first_name": "New", "last_name": "Dude"}, format='json')
print(f"Status: {response.status_code}")
print(f"Data: {response.data}")
