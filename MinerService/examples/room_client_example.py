#!/usr/bin/env python3
"""
Example WebSocket client demonstrating room management functionality
"""

import asyncio
import json
import uuid
from typing import Any, Dict

import websockets


class RoomWebSocketClient:
    """Example WebSocket client with room management capabilities"""

    def __init__(self, uri: str = "ws://localhost:8000/ws"):
        self.uri = uri
        self.client_id = str(uuid.uuid4())
        self.websocket = None
        self.rooms = set()
        self.running = False

    async def connect(self):
        """Connect to the WebSocket server"""
        try:
            self.websocket = await websockets.connect(f"{self.uri}/{self.client_id}")
            print(
                f"Connected to WebSocket server with client ID: {self.client_id}")

            # Start listening for messages
            self.running = True
            asyncio.create_task(self._listen_for_messages())

        except Exception as e:
            print(f"Failed to connect: {e}")
            raise

    async def disconnect(self):
        """Disconnect from the WebSocket server"""
        self.running = False
        if self.websocket:
            await self.websocket.close()
            print("Disconnected from WebSocket server")

    async def _listen_for_messages(self):
        """Listen for incoming messages"""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError:
                    print(f"Received non-JSON message: {message}")
        except websockets.exceptions.ConnectionClosed:
            print("WebSocket connection closed")
        except Exception as e:
            print(f"Error listening for messages: {e}")

    async def _handle_message(self, data: Dict[str, Any]):
        """Handle incoming messages"""
        message_type = data.get('type')

        if message_type == 'connected':
            print(f"✅ Connected to server: {data.get('message')}")

        elif message_type == 'room_joined':
            room_id = data.get('room_id')
            self.rooms.add(room_id)
            print(f"✅ Joined room: {room_id}")

        elif message_type == 'room_left':
            room_id = data.get('room_id')
            self.rooms.discard(room_id)
            print(f"✅ Left room: {room_id}")

        elif message_type == 'room_broadcast_sent':
            room_id = data.get('room_id')
            client_count = data.get('client_count')
            print(
                f"✅ Room broadcast sent to {client_count} clients in room {room_id}")

        elif message_type == 'client_rooms':
            rooms = data.get('rooms', [])
            self.rooms = set(rooms)
            print(f"📋 Current rooms: {list(self.rooms)}")

        elif message_type == 'error':
            print(f"❌ Error: {data.get('message')}")

        else:
            print(f"📨 Received message: {data}")

    async def join_room(self, room_id: str):
        """Join a room"""
        if not self.websocket:
            print("Not connected to server")
            return False

        message = {
            'type': 'join_room',
            'room_id': room_id
        }

        await self.websocket.send(json.dumps(message))
        print(f"🔄 Joining room: {room_id}")
        return True

    async def leave_room(self, room_id: str):
        """Leave a room"""
        if not self.websocket:
            print("Not connected to server")
            return False

        message = {
            'type': 'leave_room',
            'room_id': room_id
        }

        await self.websocket.send(json.dumps(message))
        print(f"🔄 Leaving room: {room_id}")
        return True

    async def broadcast_to_room(self, room_id: str, message: str):
        """Broadcast a message to a room"""
        if not self.websocket:
            print("Not connected to server")
            return False

        if room_id not in self.rooms:
            print(f"Not in room: {room_id}")
            return False

        broadcast_message = {
            'type': 'room_broadcast',
            'room_id': room_id,
            'message': message
        }

        await self.websocket.send(json.dumps(broadcast_message))
        print(f"📢 Broadcasting to room {room_id}: {message}")
        return True

    async def get_rooms(self):
        """Get list of rooms the client is in"""
        if not self.websocket:
            print("Not connected to server")
            return False

        message = {
            'type': 'get_rooms'
        }

        await self.websocket.send(json.dumps(message))
        print("🔄 Getting current rooms...")
        return True

    async def ping(self):
        """Send ping to server"""
        if not self.websocket:
            print("Not connected to server")
            return False

        message = {
            'type': 'ping'
        }

        await self.websocket.send(json.dumps(message))
        return True


async def main():
    """Main example function"""
    client = RoomWebSocketClient()

    try:
        # Connect to server
        await client.connect()

        # Wait a moment for connection to establish
        await asyncio.sleep(1)

        # Join some rooms
        await client.join_room("trading_room")
        await client.join_room("alerts")
        await client.join_room("general")

        # Wait for join confirmations
        await asyncio.sleep(2)

        # Get current rooms
        await client.get_rooms()
        await asyncio.sleep(1)

        # Send some messages to rooms
        await client.broadcast_to_room("trading_room", "Hello traders! How's the market today?")
        await client.broadcast_to_room("alerts", "New alert: AAPL just hit a new high!")

        # Wait for messages to be processed
        await asyncio.sleep(2)

        # Leave a room
        await client.leave_room("general")
        await asyncio.sleep(1)

        # Get updated room list
        await client.get_rooms()
        await asyncio.sleep(1)

        # Keep connection alive for a bit to see incoming messages
        print("Keeping connection alive for 10 seconds...")
        await asyncio.sleep(10)

    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
