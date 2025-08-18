#!/usr/bin/env python3
"""
Example client demonstrating integrated BarsManager + RoomManager system
"""

import asyncio
import json
import uuid
from typing import Any, Dict

import websockets


class IntegratedWebSocketClient:
    """Example WebSocket client with integrated quote/bar subscriptions"""

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

        elif message_type == 'subscribed':
            symbol = data.get('symbol')
            room_id = data.get('room_id')
            if room_id:
                self.rooms.add(room_id)
                print(
                    f"✅ Subscribed to {symbol} quotes, joined room: {room_id}")
            else:
                print(f"✅ Subscribed to {symbol} quotes (fallback method)")

        elif message_type == 'bars_subscribed':
            symbol = data.get('symbol')
            interval = data.get('interval')
            room_id = data.get('room_id')
            if room_id:
                self.rooms.add(room_id)
                print(
                    f"✅ Subscribed to {symbol} {interval} bars, joined room: {room_id}")
            else:
                print(
                    f"✅ Subscribed to {symbol} {interval} bars (fallback method)")

        elif message_type == 'quote':
            quote_data = data.get('data', {})
            symbol = quote_data.get('symbol', 'Unknown')
            price = quote_data.get('price', 0)
            change = quote_data.get('change', 0)
            print(f"📈 Quote Update - {symbol}: ${price:.2f} ({change:+.2f})")

        elif message_type == 'bars':
            bars_data = data.get('data', {})
            symbol = bars_data.get('symbol', 'Unknown')
            interval = bars_data.get('interval', 'Unknown')
            bars = bars_data.get('bars', [])
            print(
                f"📊 Bars Update - {symbol} {interval}: {len(bars)} bars received")

        elif message_type == 'quote_update':
            quote_data = data.get('data', {})
            symbol = quote_data.get('symbol', 'Unknown')
            price = quote_data.get('price', 0)
            change = quote_data.get('change', 0)
            print(
                f"🔄 Real-time Quote - {symbol}: ${price:.2f} ({change:+.2f})")

        elif message_type == 'bar_update':
            bar_data = data.get('data', {})
            symbol = bar_data.get('symbol', 'Unknown')
            interval = bar_data.get('interval', 'Unknown')
            bar = bar_data.get('bar', {})
            close = bar.get('close', 0)
            volume = bar.get('volume', 0)
            print(
                f"🔄 Real-time Bar - {symbol} {interval}: Close ${close:.2f}, Volume {volume:,}")

        elif message_type == 'room_joined':
            room_id = data.get('room_id')
            self.rooms.add(room_id)
            print(f"✅ Joined room: {room_id}")

        elif message_type == 'room_left':
            room_id = data.get('room_id')
            self.rooms.discard(room_id)
            print(f"✅ Left room: {room_id}")

        elif message_type == 'error':
            print(f"❌ Error: {data.get('message')}")

        else:
            print(f"📨 Received message: {data}")

    async def subscribe_to_quotes(self, symbol: str):
        """Subscribe to quotes for a symbol"""
        if not self.websocket:
            print("Not connected to server")
            return False

        message = {
            'type': 'subscribe',
            'symbol': symbol
        }

        await self.websocket.send(json.dumps(message))
        print(f"🔄 Subscribing to quotes for {symbol}")
        return True

    async def subscribe_to_bars(self, symbol: str, interval: str):
        """Subscribe to bars for a symbol and interval"""
        if not self.websocket:
            print("Not connected to server")
            return False

        message = {
            'type': 'subscribe_bars',
            'symbol': symbol,
            'interval': interval
        }

        await self.websocket.send(json.dumps(message))
        print(f"🔄 Subscribing to {interval} bars for {symbol}")
        return True

    async def join_room(self, room_id: str):
        """Join a specific room"""
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
        """Leave a specific room"""
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
    client = IntegratedWebSocketClient()

    try:
        # Connect to server
        await client.connect()

        # Wait a moment for connection to establish
        await asyncio.sleep(1)

        # Subscribe to some quotes
        await client.subscribe_to_quotes("AAPL")
        await client.subscribe_to_quotes("MSFT")
        await client.subscribe_to_quotes("GOOGL")

        # Wait for subscriptions to be processed
        await asyncio.sleep(2)

        # Subscribe to some bars
        await client.subscribe_to_bars("AAPL", "5m")
        await client.subscribe_to_bars("MSFT", "1m")

        # Wait for subscriptions to be processed
        await asyncio.sleep(2)

        # Get current rooms
        await client.get_rooms()
        await asyncio.sleep(1)

        # Keep connection alive to receive real-time updates
        print("🔄 Keeping connection alive to receive real-time updates...")
        print("📊 You should now see real-time quote and bar updates!")
        print("⏰ Updates will come every 1 second for quotes, every 5 seconds for bars")

        # Wait for real-time updates
        await asyncio.sleep(30)

    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
