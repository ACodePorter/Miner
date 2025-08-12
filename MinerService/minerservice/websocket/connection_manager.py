"""WebSocket connection manager with Redis support"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Set, Tuple

import redis.asyncio as redis
from fastapi import WebSocket


class WebSocketConnectionManager:
    """Manages WebSocket connections with Redis support for multi-process scaling"""

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.process_id = str(uuid.uuid4())
        self.local_connections: Dict[str, WebSocket] = {}
        self.subscribed_symbols: Set[str] = set()
        self.subscribed_bars: Set[Tuple[str, str]] = set()
        self.last_bars_ts: Dict[Tuple[str, str], int] = {}

        # Background tasks
        self.broadcast_task: Optional[asyncio.Task] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.running = False

    async def get_redis(self) -> redis.Redis:
        """Get Redis client with connection pooling and health checks"""
        if self.redis_client is None:
            await self._create_redis_connection()
        else:
            try:
                await self.redis_client.ping()
            except Exception:
                await self._reconnect_redis()

        return self.redis_client

    async def _create_redis_connection(self) -> None:
        """Create new Redis connection"""
        try:
            self.redis_client = redis.Redis(
                host='miner-redis',
                port=6379,
                db=0,
                decode_responses=True,
                password=None,
                max_connections=20,
                retry_on_timeout=True,
                health_check_interval=30,
            )
            await self.redis_client.ping()
            print(f"Redis connected for process {self.process_id}")
        except Exception as e:
            print(f"Failed to connect to Redis: {e}")
            raise

    async def _reconnect_redis(self) -> None:
        """Reconnect to Redis on connection failure"""
        try:
            await self.redis_client.close()
        except Exception:
            pass

        await self._create_redis_connection()
        print(f"Redis reconnected for process {self.process_id}")

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """Connect a new WebSocket client"""
        try:
            await websocket.accept()
            self.local_connections[client_id] = websocket

            # Store connection info in Redis
            await self._store_connection_info(client_id)
            print(f"Client {client_id} connected to process {self.process_id}")

        except Exception as e:
            print(f"Error connecting client {client_id}: {e}")
            raise

    async def _store_connection_info(self, client_id: str) -> None:
        """Store connection information in Redis"""
        redis_client = await self.get_redis()
        connection_info = {
            'client_id': client_id,
            'process_id': self.process_id,
            'connected_at': datetime.now().isoformat(),
            'last_heartbeat': datetime.now().isoformat()
        }

        async with redis_client.pipeline() as pipe:
            await pipe.hset(f"websocket:connections:{client_id}", mapping=connection_info)
            # 1 hour TTL
            await pipe.expire(f"websocket:connections:{client_id}", 3600)
            await pipe.sadd(f"websocket:processes:{self.process_id}:clients", client_id)
            await pipe.expire(f"websocket:processes:{self.process_id}:clients", 3600)
            await pipe.execute()

    async def disconnect(self, websocket: WebSocket, client_id: str) -> None:
        """Disconnect a WebSocket client"""
        try:
            if client_id in self.local_connections:
                del self.local_connections[client_id]

            # Remove from Redis
            await self._remove_connection_info(client_id)
            print(
                f"Client {client_id} disconnected from process {self.process_id}")

        except Exception as e:
            print(f"Error disconnecting client {client_id}: {e}")

    async def _remove_connection_info(self, client_id: str) -> None:
        """Remove connection information from Redis"""
        redis_client = await self.get_redis()
        async with redis_client.pipeline() as pipe:
            await pipe.delete(f"websocket:connections:{client_id}")
            await pipe.srem(f"websocket:processes:{self.process_id}:clients", client_id)
            await pipe.execute()

    async def send_personal_message(self, message: str, client_id: str) -> bool:
        """Send message to a specific client"""
        if client_id in self.local_connections:
            websocket = self.local_connections[client_id]
            try:
                await websocket.send_text(message)
                return True
            except Exception as e:
                print(f"Error sending message to {client_id}: {e}")
                # Remove broken connection
                await self.disconnect(websocket, client_id)
                return False
        return False

    async def broadcast(self, message: str) -> None:
        """Broadcast to all connections in this process"""
        disconnected_clients = []

        for client_id in list(self.local_connections.keys()):
            success = await self.send_personal_message(message, client_id)
            if not success:
                disconnected_clients.append(client_id)

        # Clean up disconnected clients
        for client_id in disconnected_clients:
            if client_id in self.local_connections:
                await self.disconnect(self.local_connections[client_id], client_id)

    async def broadcast_to_all_processes(self, message: str) -> None:
        """Broadcast message to all processes via Redis pub/sub"""
        try:
            redis_client = await self.get_redis()
            await redis_client.publish('websocket:broadcast', json.dumps({
                'message': message,
                'process_id': self.process_id,
                'timestamp': datetime.now().isoformat()
            }))
        except Exception as e:
            print(f"Error broadcasting message: {e}")

    async def subscribe_symbol(self, symbol: str) -> None:
        """Subscribe to a symbol for real-time quotes"""
        if symbol not in self.subscribed_symbols:
            self.subscribed_symbols.add(symbol)

            try:
                redis_client = await self.get_redis()
                await redis_client.sadd('websocket:subscribed_symbols', symbol)
                print(f"Subscribed to symbol: {symbol}")
            except Exception as e:
                print(f"Error subscribing to symbol {symbol}: {e}")

    async def subscribe_bars(self, symbol: str, interval: str) -> None:
        """Subscribe to bars updates for a symbol and interval"""
        key = (symbol.upper(), interval)
        if key not in self.subscribed_bars:
            self.subscribed_bars.add(key)
            try:
                redis_client = await self.get_redis()
                await redis_client.sadd('websocket:subscribed_bars', f"{key[0]}|{key[1]}")
                print(f"Subscribed to bars: {key[0]} {key[1]}")
            except Exception as e:
                print(f"Error subscribing to bars {key}: {e}")

    async def unsubscribe_bars(self, symbol: str, interval: str) -> None:
        """Unsubscribe from bars updates"""
        key = (symbol.upper(), interval)
        if key in self.subscribed_bars:
            self.subscribed_bars.remove(key)
            try:
                redis_client = await self.get_redis()
                await redis_client.srem('websocket:subscribed_bars', f"{key[0]}|{key[1]}")
            except Exception:
                pass

    async def get_all_connections(self) -> list:
        """Get all active connections across all processes"""
        try:
            redis_client = await self.get_redis()
            connections = await redis_client.keys('websocket:connections:*')
            return connections
        except Exception as e:
            print(f"Error getting connections: {e}")
            return []

    async def start_broadcast_listener(self) -> None:
        """Start listening for broadcast messages from other processes"""
        try:
            redis_client = await self.get_redis()
            pubsub = redis_client.pubsub()
            await pubsub.subscribe('websocket:broadcast')

            async def listen_for_broadcasts():
                try:
                    async for message in pubsub.listen():
                        if message['type'] == 'message':
                            try:
                                data = json.loads(message['data'])
                                # Only process messages from other processes
                                if data.get('process_id') != self.process_id:
                                    await self.broadcast(data['message'])
                            except Exception as e:
                                print(
                                    f"Error processing broadcast message: {e}")
                except Exception as e:
                    print(f"Broadcast listener error: {e}")
                finally:
                    await pubsub.close()

            self.broadcast_task = asyncio.create_task(listen_for_broadcasts())
            print(f"Broadcast listener started for process {self.process_id}")

        except Exception as e:
            print(f"Error starting broadcast listener: {e}")

    async def start_heartbeat(self) -> None:
        """Start heartbeat mechanism to detect stale connections"""
        async def heartbeat_loop():
            while self.running:
                try:
                    await asyncio.sleep(30)  # Heartbeat every 30 seconds

                    # Update heartbeat for all local connections
                    redis_client = await self.get_redis()
                    current_time = datetime.now().isoformat()

                    for client_id in list(self.local_connections.keys()):
                        try:
                            await redis_client.hset(
                                f"websocket:connections:{client_id}",
                                'last_heartbeat',
                                current_time
                            )
                        except Exception as e:
                            print(
                                f"Error updating heartbeat for {client_id}: {e}")

                    # Clean up stale connections from other processes
                    await self.cleanup_stale_connections()

                except Exception as e:
                    print(f"Heartbeat error: {e}")
                    await asyncio.sleep(5)  # Wait before retrying

        self.heartbeat_task = asyncio.create_task(heartbeat_loop())
        print(f"Heartbeat started for process {self.process_id}")

    async def cleanup_stale_connections(self) -> None:
        """Clean up stale connections from other processes"""
        try:
            redis_client = await self.get_redis()
            current_time = datetime.now()

            # Get all connection keys
            connection_keys = await redis_client.keys('websocket:connections:*')

            for key in connection_keys:
                try:
                    # Check if connection is stale (no heartbeat for 2 minutes)
                    last_heartbeat_str = await redis_client.hget(key, 'last_heartbeat')
                    if last_heartbeat_str:
                        last_heartbeat = datetime.fromisoformat(
                            last_heartbeat_str)
                        if (current_time - last_heartbeat).total_seconds() > 120:
                            # Connection is stale, remove it
                            await redis_client.delete(key)
                            print(f"Cleaned up stale connection: {key}")
                except Exception as e:
                    print(f"Error checking connection {key}: {e}")

        except Exception as e:
            print(f"Error during cleanup: {e}")

    async def startup(self) -> None:
        """Initialize the connection manager"""
        self.running = True
        await self.start_broadcast_listener()
        await self.start_heartbeat()
        print(
            f"WebSocketConnectionManager started for process {self.process_id}")

    async def shutdown(self) -> None:
        """Clean shutdown of the connection manager"""
        self.running = False

        # Close all local connections
        for client_id in list(self.local_connections.keys()):
            try:
                websocket = self.local_connections[client_id]
                await websocket.close()
            except:
                pass

        # Clean up Redis
        if self.redis_client:
            try:
                await self.redis_client.close()
            except:
                pass

        # Cancel background tasks
        if self.broadcast_task:
            self.broadcast_task.cancel()
        if self.heartbeat_task:
            self.heartbeat_task.cancel()

        print(
            f"WebSocketConnectionManager shutdown for process {self.process_id}")

    # Utility methods for external services to use
    def get_subscribed_symbols(self) -> Set[str]:
        """Get all subscribed symbols for this process"""
        return self.subscribed_symbols.copy()

    def get_subscribed_bars(self) -> Set[Tuple[str, str]]:
        """Get all subscribed bars for this process"""
        return self.subscribed_bars.copy()

    def get_last_bars_timestamp(self, symbol: str, interval: str) -> Optional[int]:
        """Get the last bars timestamp for a symbol/interval pair"""
        return self.last_bars_ts.get((symbol.upper(), interval))

    def set_last_bars_timestamp(self, symbol: str, interval: str, timestamp: int) -> None:
        """Set the last bars timestamp for a symbol/interval pair"""
        self.last_bars_ts[(symbol.upper(), interval)] = timestamp

    def get_local_connections_count(self) -> int:
        """Get the number of local connections"""
        return len(self.local_connections)

    def get_process_id(self) -> str:
        """Get the process ID"""
        return self.process_id

    def is_running(self) -> bool:
        """Check if the manager is running"""
        return self.running
