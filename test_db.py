import os
import django
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings') 
try:
    django.setup()
except Exception as e:
    print(f"Error setting up django: {e}")
    sys.exit(1)

from api.messaging.models import ChatThread, ThreadParticipant
from django.core.cache import cache

thread_id = "5e40e9ec-292b-4600-b389-d750ea8cba0f"

print(f"=== Inspecting Thread {thread_id} ===")
try:
    thread = ChatThread.objects.get(id=thread_id)
    print(f"Thread: {thread.id}, Type: {thread.thread_type}")
    
    participants = ThreadParticipant.objects.filter(thread=thread)
    for p in participants:
        print(f"  Participant: User {p.user.id} ({p.user.username}), left_at: {p.left_at}")
        
        # Check cache
        cache_key = f"user_inbox_{p.user.id}_page_1"
        cached_data = cache.get(cache_key)
        if cached_data:
            print(f"  Cache for {p.user.username} EXISTS!")
        else:
            print(f"  Cache for {p.user.username} is EMPTY.")
            
except Exception as e:
    print(f"Error: {e}")
