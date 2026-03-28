import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
settings.ALLOWED_HOSTS = ['*']

from api.users.models import User, Profile
from rest_framework.test import APIClient
from django.contrib.gis.geos import Point

# Create a test user
email = "repro_test_v2@example.com"
User.objects.filter(email=email).delete()
user = User.objects.create_user(email=email, password="password123")
profile, _ = Profile.objects.get_or_create(user=user)

client = APIClient()
client.force_authenticate(user=user)

# Try to PATCH with a list for location_point
data = {
    "location_point": [90.4125, 23.8103]
}

print(f"Testing PATCH /api/users/profile/ with data: {data}")
try:
    response = client.patch('/api/users/profile/', data, format='json')
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("Success: Profile updated correctly.")
        data = response.data
        location = data.get("location_point")
        print(f"location_point in response: {location}")
        if isinstance(location, list) and len(location) == 2:
            print("Verified: location_point is a list [lng, lat].")
        else:
            print(f"FAILED: location_point is {type(location)}: {location}")
    elif response.status_code == 500:
        print("Error: 500 Internal Server Error")
    else:
        print(f"Status: {response.status_code}")
        print(f"Response Data: {response.data}")
except Exception as e:
    print(f"Caught exception: {e}")
