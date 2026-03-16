import json
from django.utils import timezone
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import ThreadParticipant
from . import services

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or self.user.is_anonymous:
            await self.close()
            return

        # Join a personal group to receive notifications intended for this user
        self.user_group = f"user_{self.user.id}"
        await self.channel_layer.group_add(
            self.user_group,
            self.channel_name
        )

        await self.set_user_online(True)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "user_group"):
            await self.set_user_online(False)
            await self.channel_layer.group_discard(
                self.user_group,
                self.channel_name
            )

    @database_sync_to_async
    def set_user_online(self, is_online):
        self.user.is_online = is_online
        self.user.last_active = timezone.now()
        self.user.save(update_fields=["is_online", "last_active"])

    async def receive(self, text_data):
        """
        Handle incoming WebSocket messages from client.
        Currently used for real-time pulses, e.g., 'marking_as_read'.
        """
        try:
            data = json.loads(text_data)
            action = data.get("action")
            
            if action == "mark_read":
                thread_id = data.get("thread_id")
                if thread_id:
                    await self.handle_mark_read(thread_id)
                    
        except Exception:
            pass

    async def handle_mark_read(self, thread_id):
        # Delegate to service (wrapped in sync_to_async)
        await database_sync_to_async(services.mark_messages_read)(self.user, thread_id)
        
        # Broadcast the 'read' event to other participants in the thread
        # Note: In a production app with 1M users, we avoid putting 1M users 
        # in one group. Instead, we pull participants and notify their personal groups.
        participants = await self.get_thread_participants(thread_id)
        for p_id in participants:
            if str(p_id) != str(self.user.id):
                await self.channel_layer.group_send(
                    f"user_{p_id}",
                    {
                        "type": "message_read",
                        "thread_id": thread_id,
                        "reader_id": str(self.user.id)
                    }
                )

    @database_sync_to_async
    def get_thread_participants(self, thread_id):
        return list(
            ThreadParticipant.objects.filter(thread_id=thread_id, left_at__isnull=True)
            .values_list("user_id", flat=True)
            .distinct()
        )

    # ──────────────────────────────────────────────
    # Group message handlers
    # ──────────────────────────────────────────────

    async def chat_message(self, event):
        """Receive new message from group and send to state."""
        await self.send(text_data=json.dumps({
            "type": "new_message",
            "message": event["message"]
        }))

    async def message_read(self, event):
        """Notify client that a message was read."""
        await self.send(text_data=json.dumps({
            "type": "message_read",
            "thread_id": event["thread_id"],
            "reader_id": event["reader_id"]
        }))
