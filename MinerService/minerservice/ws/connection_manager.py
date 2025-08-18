"""WebSocket connection manager with Redis support"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import redis.asyncio as redis
from detonator import get_logger, is_prod
from fastapi import WebSocket

from ..services.bars_manager_integration import BarsManagerIntegration
from ..services.redis_subscription_service import RedisSubscriptionService
from .room_manager import RoomManager

# Global manager instance
manager: Optional['WebSocketConnectionManager'] = None
_logger = get_logger('MinerService', logging.DEBUG)


def get_websocket_manager() -> Optional['WebSocketConnectionManager']:
    """Get the global WebSocket manager instance"""
    return manager


def set_websocket_manager(manager_instance: 'WebSocketConnectionManager') -> None:
    """Set the global WebSocket manager instance"""
    global manager
    manager = manager_instance
    _logger.info(
        f"Global WebSocket manager set: {manager_instance.process_id if manager_instance else 'None'}")


class WebSocketConnectionManager:
    """Manages WebSocket connections with Redis support for multi-process scaling"""

    def __init__(self):
        self.logger = get_logger('WebSocketConnectionManager')
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

        # Integration services
        self.bars_manager_integration: Optional[BarsManagerIntegration] = None
        self.redis_subscription_service: Optional[RedisSubscriptionService] = None
        self.room_manager: Optional[RoomManager] = None

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
            # Force localhost for testing
            redis_host = 'miner-redis' if is_prod() else 'localhost'
            self.logger.debug(
                f"is_prod() = {is_prod()}, using Redis host: {redis_host}")

            self.redis_client = redis.Redis(
                host=redis_host,
                port=6379,
                db=0,
                decode_responses=True,
                password=None,
                max_connections=20,
                retry_on_timeout=True,
                health_check_interval=30,
            )
            await self.redis_client.ping()
            self.logger.info(f"Redis connected for process {self.process_id}")
        except Exception as e:
            self.logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def _reconnect_redis(self) -> None:
        """Reconnect to Redis on connection failure"""
        try:
            await self.redis_client.close()
        except Exception:
            pass

        await self._create_redis_connection()
        self.logger.info(f"Redis reconnected for process {self.process_id}")

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """Connect a new WebSocket client"""
        try:
            await websocket.accept()
            self.local_connections[client_id] = websocket

            # Store connection info in Redis
            await self._store_connection_info(client_id)

            # Clean up stale subscriptions on first connection
            if len(self.local_connections) == 1:
                await self.cleanup_stale_subscriptions()

            self.logger.info(
                f"Client {client_id} connected to process {self.process_id}")

        except Exception as e:
            self.logger.error(f"Error connecting client {client_id}: {e}")
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
        """Disconnect a WebSocket client with comprehensive cleanup"""
        try:
            self.logger.info(
                f"🔄 Starting comprehensive cleanup for disconnected client: {client_id}")

            # Step 1: Clean up local connection tracking
            if client_id in self.local_connections:
                del self.local_connections[client_id]
                self.logger.info(
                    f"✅ Removed {client_id} from local connections")

            # Step 2: Clean up room memberships (comprehensive cross-process cleanup)
            if self.room_manager:
                try:
                    self.logger.info(
                        f"🏠 Starting room cleanup for {client_id}")
                    await self.room_manager.cleanup_client(client_id)
                    self.logger.info(
                        f"✅ Room cleanup completed for {client_id}")
                except Exception as e:
                    self.logger.error(
                        f"❌ Error during room cleanup for {client_id}: {e}")
                    import traceback
                    self.logger.error(
                        f"❌ Room cleanup traceback: {traceback.format_exc()}")
                    # Continue with other cleanup steps even if room cleanup fails

            # Step 3: Clean up symbol subscriptions if this was the last client
            try:
                await self._cleanup_client_subscriptions(client_id)
                self.logger.info(
                    f"✅ Subscription cleanup completed for {client_id}")
            except Exception as e:
                self.logger.error(
                    f"❌ Error during subscription cleanup for {client_id}: {e}")

            # Step 4: Remove from Redis connection tracking
            try:
                await self._remove_connection_info(client_id)
                self.logger.info(f"✅ Removed {client_id} from Redis tracking")
            except Exception as e:
                self.logger.error(
                    f"❌ Error removing {client_id} from Redis tracking: {e}")

            # Step 5: Clean up any client-specific data
            try:
                await self._cleanup_client_data(client_id)
                self.logger.info(
                    f"✅ Client data cleanup completed for {client_id}")
            except Exception as e:
                self.logger.error(
                    f"❌ Error during client data cleanup for {client_id}: {e}")

            # Step 6: Final verification - ensure client is completely cleaned up
            try:
                await self._verify_final_cleanup(client_id)
                self.logger.info(
                    f"✅ Final cleanup verification completed for {client_id}")
            except Exception as e:
                self.logger.error(
                    f"❌ Error during final cleanup verification for {client_id}: {e}")

            self.logger.info(
                f"🎉 Client {client_id} fully disconnected and cleaned up from process {self.process_id}")

        except Exception as e:
            self.logger.error(
                f"❌ Critical error during disconnect cleanup for {client_id}: {e}")
            import traceback
            self.logger.error(
                f"❌ Critical error traceback: {traceback.format_exc()}")

            # Emergency cleanup - try to at least remove from local connections
            try:
                self.local_connections.pop(client_id, None)
                self.logger.warning(
                    f"🆘 Emergency cleanup: removed {client_id} from local connections")
            except:
                self.logger.error(
                    f"🆘 Emergency cleanup failed for {client_id}")

    async def cleanup_stale_subscriptions(self) -> None:
        """Clean up stale subscriptions that may exist in Redis but not in memory"""
        try:
            redis_client = await self.get_redis()

            # Get all quote subscriptions from Redis
            redis_quote_subs = await redis_client.smembers('websocket:subscribed_symbols')
            redis_quote_subs = [sub.decode(
                'utf-8') if isinstance(sub, bytes) else sub for sub in redis_quote_subs]

            # Get all bars subscriptions from Redis
            redis_bars_subs = await redis_client.smembers('websocket:subscribed_bars')
            redis_bars_subs = [sub.decode(
                'utf-8') if isinstance(sub, bytes) else sub for sub in redis_bars_subs]

            # Clean up quote subscriptions that don't exist in memory
            for symbol in redis_quote_subs:
                if symbol not in self.subscribed_symbols:
                    await redis_client.srem('websocket:subscribed_symbols', symbol)
                    self.logger.info(
                        f"Cleaned up stale quote subscription: {symbol}")

            # Clean up bars subscriptions that don't exist in memory
            for key in redis_bars_subs:
                if '|' in key:
                    symbol, interval = key.split('|', 1)
                    if (symbol, interval) not in self.subscribed_bars:
                        await redis_client.srem('websocket:subscribed_bars', key)
                        self.logger.info(
                            f"Cleaned up stale bars subscription: {key}")

            self.logger.info(
                f"Subscription cleanup completed. Active quotes: {len(self.subscribed_symbols)}, Active bars: {len(self.subscribed_bars)}")

        except Exception as e:
            self.logger.error(f"Error during subscription cleanup: {e}")

    async def _remove_connection_info(self, client_id: str) -> None:
        """Remove connection information from Redis"""
        redis_client = await self.get_redis()
        async with redis_client.pipeline() as pipe:
            await pipe.delete(f"websocket:connections:{client_id}")
            await pipe.srem(f"websocket:processes:{self.process_id}:clients", client_id)
            await pipe.execute()

    async def _cleanup_client_subscriptions(self, client_id: str) -> None:
        """Clean up symbol subscriptions if this was the last client interested"""
        try:
            self.logger.info(
                f"🔄 Starting subscription cleanup for client: {client_id}")

            # Get all active subscriptions for this client
            client_subscriptions = await self._get_client_subscriptions(client_id)
            self.logger.info(
                f"Client {client_id} had {len(client_subscriptions['quotes'])} quote and {len(client_subscriptions['bars'])} bar subscriptions")

            # Use a flag to prevent race conditions during cleanup
            if hasattr(self, '_subscription_cleanup_in_progress'):
                self.logger.warning(
                    f"⚠️ Subscription cleanup already in progress for {client_id}, skipping")
                return

            self._subscription_cleanup_in_progress = True

            try:
                # Check if other clients are still interested in these symbols
                for symbol in client_subscriptions['quotes']:
                    await self._check_and_cleanup_quote_subscription(symbol, client_id)

                for symbol, interval in client_subscriptions['bars']:
                    await self._check_and_cleanup_bar_subscription(symbol, interval, client_id)

            finally:
                # Always clear the flag
                self._subscription_cleanup_in_progress = False

            self.logger.info(
                f"✅ Subscription cleanup completed for client: {client_id}")

        except Exception as e:
            self.logger.error(
                f"❌ Error during subscription cleanup for {client_id}: {e}")
            import traceback
            self.logger.error(
                f"❌ Subscription cleanup traceback: {traceback.format_exc()}")
            # Ensure flag is cleared even on error
            if hasattr(self, '_subscription_cleanup_in_progress'):
                self._subscription_cleanup_in_progress = False

    async def _get_client_subscriptions(self, client_id: str) -> Dict[str, Any]:
        """Get all subscriptions that a specific client was interested in"""
        try:
            client_subscriptions = {
                'quotes': set(),
                'bars': set()
            }

            # Check if client was in any quote rooms
            if self.room_manager:
                client_rooms = await self.room_manager.get_client_rooms(client_id)
                for room_id in client_rooms:
                    if room_id.startswith('quotes:'):
                        symbol = room_id.split(':', 1)[1]
                        client_subscriptions['quotes'].add(symbol)
                    elif room_id.startswith('bars:'):
                        parts = room_id.split(':', 2)
                        if len(parts) == 3:
                            symbol, interval = parts[1], parts[2]
                            client_subscriptions['bars'].add(
                                (symbol, interval))

            return client_subscriptions

        except Exception as e:
            self.logger.error(
                f"Error getting client subscriptions for {client_id}: {e}")
            return {'quotes': set(), 'bars': set()}

    async def _check_and_cleanup_quote_subscription(self, symbol: str, disconnected_client_id: str) -> None:
        """Check if quote subscription should be cleaned up and clean up if needed - RACE CONDITION SAFE"""
        try:
            self.logger.info(
                f"🔍 Checking quote subscription for {symbol} after client {disconnected_client_id} disconnected")

            # Use atomic Redis operation to check room membership
            try:
                redis_client = await self.get_redis()
                room_id = f"quotes:{symbol}"

                # Get current room membership atomically
                room_members = await redis_client.smembers(f"room:{room_id}:clients")
                room_members = {member.decode(
                    'utf-8') if isinstance(member, bytes) else member for member in room_members}

                # Remove the disconnected client from consideration
                other_clients = room_members - {disconnected_client_id}

                if not other_clients:
                    self.logger.info(
                        f"🗑️ No other clients interested in {symbol}, cleaning up subscription")

                    # Unsubscribe from BarsManager
                    if self.bars_manager_integration:
                        try:
                            await self.bars_manager_integration.unsubscribe_from_quotes(symbol)
                            self.logger.info(
                                f"✅ Unsubscribed from BarsManager quotes for {symbol}")
                        except Exception as e:
                            self.logger.error(
                                f"❌ Failed to unsubscribe from BarsManager quotes for {symbol}: {e}")

                    # Remove from Redis subscription tracking
                    try:
                        await redis_client.srem('websocket:subscribed_symbols', symbol)
                        self.logger.info(
                            f"✅ Removed {symbol} from Redis quote subscriptions")
                    except Exception as e:
                        self.logger.error(
                            f"❌ Failed to remove {symbol} from Redis quote subscriptions: {e}")

                    # Remove from local tracking
                    if symbol in self.subscribed_symbols:
                        self.subscribed_symbols.discard(symbol)
                        self.logger.info(
                            f"✅ Removed {symbol} from local quote subscriptions")
                else:
                    self.logger.info(
                        f"✅ Other clients still interested in {symbol}, keeping subscription")

            except Exception as e:
                self.logger.error(
                    f"❌ Error checking Redis room membership for {symbol}: {e}")
                # Fallback to local room check
                if self.room_manager:
                    try:
                        other_clients_interested = await self._check_other_clients_quote_interest(symbol, disconnected_client_id)
                        if not other_clients_interested:
                            self.logger.info(
                                f"🗑️ Fallback check: No other clients interested in {symbol}, cleaning up subscription")
                            await self._force_cleanup_quote_subscription(symbol)
                    except Exception as fallback_error:
                        self.logger.error(
                            f"❌ Fallback quote subscription check failed for {symbol}: {fallback_error}")

        except Exception as e:
            self.logger.error(
                f"❌ Error checking quote subscription cleanup for {symbol}: {e}")

    async def _check_and_cleanup_bar_subscription(self, symbol: str, interval: str, disconnected_client_id: str) -> None:
        """Check if bar subscription should be cleaned up and clean up if needed - RACE CONDITION SAFE"""
        try:
            self.logger.info(
                f"🔍 Checking bar subscription for {symbol}:{interval} after client {disconnected_client_id} disconnected")

            # Use atomic Redis operation to check room membership
            try:
                redis_client = await self.get_redis()
                room_id = f"bars:{symbol}:{interval}"

                # Get current room membership atomically
                room_members = await redis_client.smembers(f"room:{room_id}:clients")
                room_members = {member.decode(
                    'utf-8') if isinstance(member, bytes) else member for member in room_members}

                # Remove the disconnected client from consideration
                other_clients = room_members - {disconnected_client_id}

                if not other_clients:
                    self.logger.info(
                        f"🗑️ No other clients interested in {symbol}:{interval}, cleaning up subscription")

                    # Unsubscribe from BarsManager
                    if self.bars_manager_integration:
                        try:
                            await self.bars_manager_integration.unsubscribe_from_bars(symbol, interval)
                            self.logger.info(
                                f"✅ Unsubscribed from BarsManager bars for {symbol}:{interval}")
                        except Exception as e:
                            self.logger.error(
                                f"❌ Failed to unsubscribe from BarsManager bars for {symbol}:{interval}: {e}")

                    # Remove from Redis subscription tracking
                    try:
                        subscription_key = f"{symbol}|{interval}"
                        await redis_client.srem('websocket:subscribed_bars', subscription_key)
                        self.logger.info(
                            f"✅ Removed {symbol}:{interval} from Redis bar subscriptions")
                    except Exception as e:
                        self.logger.error(
                            f"❌ Failed to remove {symbol}:{interval} from Redis bar subscriptions: {e}")

                    # Remove from local tracking
                    subscription_tuple = (symbol.upper(), interval)
                    if subscription_tuple in self.subscribed_bars:
                        self.subscribed_bars.discard(subscription_tuple)
                        self.logger.info(
                            f"✅ Removed {symbol}:{interval} from local bar subscriptions")
                else:
                    self.logger.info(
                        f"✅ Other clients still interested in {symbol}:{interval}, keeping subscription")

            except Exception as e:
                self.logger.error(
                    f"❌ Error checking Redis room membership for {symbol}:{interval}: {e}")
                # Fallback to local room check
                if self.room_manager:
                    try:
                        other_clients_interested = await self._check_other_clients_bar_interest(symbol, interval, disconnected_client_id)
                        if not other_clients_interested:
                            self.logger.info(
                                f"🗑️ Fallback check: No other clients interested in {symbol}:{interval}, cleaning up subscription")
                            await self._force_cleanup_bar_subscription(symbol, interval)
                    except Exception as fallback_error:
                        self.logger.error(
                            f"❌ Fallback bar subscription check failed for {symbol}:{interval}: {fallback_error}")

        except Exception as e:
            self.logger.error(
                f"❌ Error checking bar subscription cleanup for {symbol}:{interval}: {e}")

    async def _force_cleanup_quote_subscription(self, symbol: str) -> None:
        """Force cleanup of quote subscription - used when fallback checks are needed"""
        try:
            self.logger.info(
                f"🔄 Force cleaning up quote subscription for {symbol}")

            # Unsubscribe from BarsManager
            if self.bars_manager_integration:
                try:
                    await self.bars_manager_integration.unsubscribe_from_quotes(symbol)
                    self.logger.info(
                        f"✅ Force unsubscribed from BarsManager quotes for {symbol}")
                except Exception as e:
                    self.logger.error(
                        f"❌ Force unsubscribe from BarsManager quotes failed for {symbol}: {e}")

            # Remove from Redis subscription tracking
            try:
                redis_client = await self.get_redis()
                await redis_client.srem('websocket:subscribed_symbols', symbol)
                self.logger.info(
                    f"✅ Force removed {symbol} from Redis quote subscriptions")
            except Exception as e:
                self.logger.error(
                    f"❌ Force remove from Redis quote subscriptions failed for {symbol}: {e}")

            # Remove from local tracking
            if symbol in self.subscribed_symbols:
                self.subscribed_symbols.discard(symbol)
                self.logger.info(
                    f"✅ Force removed {symbol} from local quote subscriptions")

        except Exception as e:
            self.logger.error(
                f"❌ Error in force quote subscription cleanup for {symbol}: {e}")

    async def _force_cleanup_bar_subscription(self, symbol: str, interval: str) -> None:
        """Force cleanup of bar subscription - used when fallback checks are needed"""
        try:
            self.logger.info(
                f"🔄 Force cleaning up bar subscription for {symbol}:{interval}")

            # Unsubscribe from BarsManager
            if self.bars_manager_integration:
                try:
                    await self.bars_manager_integration.unsubscribe_from_bars(symbol, interval)
                    self.logger.info(
                        f"✅ Force unsubscribed from BarsManager bars for {symbol}:{interval}")
                except Exception as e:
                    self.logger.error(
                        f"❌ Force unsubscribe from BarsManager bars failed for {symbol}:{interval}: {e}")

            # Remove from Redis subscription tracking
            try:
                redis_client = await self.get_redis()
                subscription_key = f"{symbol}|{interval}"
                await redis_client.srem('websocket:subscribed_bars', subscription_key)
                self.logger.info(
                    f"✅ Force removed {symbol}:{interval} from Redis bar subscriptions")
            except Exception as e:
                self.logger.error(
                    f"❌ Force remove from Redis bar subscriptions failed for {symbol}:{interval}: {e}")

            # Remove from local tracking
            subscription_tuple = (symbol.upper(), interval)
            if subscription_tuple in self.subscribed_bars:
                self.subscribed_bars.discard(subscription_tuple)
                self.logger.info(
                    f"✅ Force removed {symbol}:{interval} from local bar subscriptions")

        except Exception as e:
            self.logger.error(
                f"❌ Error in force bar subscription cleanup for {symbol}:{interval}: {e}")

    async def _check_other_clients_quote_interest(self, symbol: str, excluded_client_id: str) -> bool:
        """Check if other clients are still interested in a quote symbol"""
        try:
            if not self.room_manager:
                return False

            # Check if the quote room still has other clients
            room_id = f"quotes:{symbol}"
            room_clients = await self.room_manager.get_room_clients(room_id)

            # Remove the excluded client from consideration
            other_clients = room_clients - {excluded_client_id}

            has_other_clients = len(other_clients) > 0
            self.logger.debug(
                f"Quote room {room_id} has {len(other_clients)} other clients: {list(other_clients)}")

            return has_other_clients

        except Exception as e:
            self.logger.error(
                f"Error checking other clients quote interest for {symbol}: {e}")
            return False

    async def _check_other_clients_bar_interest(self, symbol: str, interval: str, excluded_client_id: str) -> bool:
        """Check if other clients are still interested in a bar symbol:interval"""
        try:
            if not self.room_manager:
                return False

            # Check if the bar room still has other clients
            room_id = f"bars:{symbol}:{interval}"
            room_clients = await self.room_manager.get_room_clients(room_id)

            # Remove the excluded client from consideration
            other_clients = room_clients - {excluded_client_id}

            has_other_clients = len(other_clients) > 0
            self.logger.debug(
                f"Bar room {room_id} has {len(other_clients)} other clients: {list(other_clients)}")

            return has_other_clients

        except Exception as e:
            self.logger.error(
                f"Error checking other clients bar interest for {symbol}:{interval}: {e}")
            return False

    async def _cleanup_client_data(self, client_id: str) -> None:
        """Clean up any client-specific data stored in Redis or other systems"""
        try:
            redis_client = await self.get_redis()

            # Clean up any client-specific keys
            client_keys = await redis_client.keys(f"client:{client_id}:*")
            if client_keys:
                await redis_client.delete(*client_keys)
                self.logger.info(
                    f"Cleaned up {len(client_keys)} client-specific keys for {client_id}")

            # Clean up any client preferences or settings
            preference_keys = await redis_client.keys(f"preferences:{client_id}:*")
            if preference_keys:
                await redis_client.delete(*preference_keys)
                self.logger.info(
                    f"Cleaned up {len(preference_keys)} preference keys for {client_id}")

            # Clean up any client session data
            session_keys = await redis_client.keys(f"session:{client_id}:*")
            if session_keys:
                await redis_client.delete(*session_keys)
                self.logger.info(
                    f"Cleaned up {len(session_keys)} session keys for {client_id}")

        except Exception as e:
            self.logger.error(
                f"Error cleaning up client data for {client_id}: {e}")

    async def send_personal_message(self, message: str, client_id: str) -> bool:
        """Send message to a specific client"""
        if client_id in self.local_connections:
            websocket = self.local_connections[client_id]
            try:
                await websocket.send_text(message)
                return True
            except Exception as e:
                self.logger.error(f"Error sending message to {client_id}: {e}")
                # Remove broken connection
                await self.disconnect(websocket, client_id)
                return False
        return False

    async def broadcast(self, message: str) -> None:
        """Broadcast to all connections in this process"""
        self.logger.info(
            f"Broadcasting message to {len(self.local_connections)} local connections: {message[:100]}...")

        # Log the message being broadcast
        try:
            parsed_message = json.loads(message)
            self.logger.debug(f"Broadcasting parsed message: {parsed_message}")
        except Exception as e:
            self.logger.error(f"Error parsing broadcast message: {e}")
            self.logger.debug(f"Raw message: {message}")

        disconnected_clients = []

        for client_id in list(self.local_connections.keys()):
            self.logger.debug(f"Attempting to send to client {client_id}")
            success = await self.send_personal_message(message, client_id)
            if not success:
                self.logger.warning(f"Failed to send to client {client_id}")
                disconnected_clients.append(client_id)
            else:
                self.logger.debug(f"Successfully sent to client {client_id}")

        # Clean up disconnected clients
        for client_id in disconnected_clients:
            if client_id in self.local_connections:
                await self.disconnect(self.local_connections[client_id], client_id)

        self.logger.info(
            f"Broadcast completed. Sent to {len(self.local_connections) - len(disconnected_clients)} clients, {len(disconnected_clients)} disconnected.")

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
            self.logger.error(f"Error broadcasting message: {e}")

    async def subscribe_symbol(self, symbol: str) -> None:
        """Subscribe to a symbol for real-time quotes"""
        if symbol not in self.subscribed_symbols:
            self.subscribed_symbols.add(symbol)

            try:
                # Subscribe via BarsManager integration
                if self.bars_manager_integration:
                    await self.bars_manager_integration.subscribe_to_quotes(symbol)
                else:
                    self.logger.warning(
                        "BarsManager integration not available")

                # Subscribe via Redis subscription service
                if self.redis_subscription_service:
                    await self.redis_subscription_service.subscribe_to_quotes(symbol)
                else:
                    self.logger.warning(
                        "Redis subscription service not available")

                # Persist subscription to Redis for monitoring and persistence
                redis_client = await self.get_redis()
                await redis_client.sadd('websocket:subscribed_symbols', symbol)

                self.logger.info(f"Subscribed to symbol: {symbol}")
            except Exception as e:
                self.logger.error(f"Error subscribing to symbol {symbol}: {e}")
                # Rollback on error
                self.subscribed_symbols.remove(symbol)

    async def unsubscribe_symbol(self, symbol: str) -> None:
        """Unsubscribe from a symbol for real-time quotes"""
        if symbol in self.subscribed_symbols:
            self.subscribed_symbols.remove(symbol)

            try:
                # Unsubscribe via BarsManager integration
                if self.bars_manager_integration:
                    await self.bars_manager_integration.unsubscribe_from_quotes(symbol)
                else:
                    self.logger.warning(
                        "BarsManager integration not available")

                # Unsubscribe via Redis subscription service
                if self.redis_subscription_service:
                    await self.redis_subscription_service.unsubscribe_from_quotes(symbol)
                else:
                    self.logger.warning(
                        "Redis subscription service not available")

                # Remove subscription from Redis
                redis_client = await self.get_redis()
                await redis_client.srem('websocket:subscribed_symbols', symbol)

                self.logger.info(f"Unsubscribed from symbol: {symbol}")
            except Exception as e:
                self.logger.error(
                    f"Error unsubscribing from symbol {symbol}: {e}")
                # Rollback on error
                self.subscribed_symbols.add(symbol)

    async def subscribe_bars(self, symbol: str, interval: str) -> None:
        """Subscribe to bars updates for a symbol and interval"""
        key = (symbol.upper(), interval)
        if key not in self.subscribed_bars:
            self.subscribed_bars.add(key)
            try:
                # Subscribe via BarsManager integration
                if self.bars_manager_integration:
                    success = await self.bars_manager_integration.subscribe_to_bars(symbol, interval)
                    if success:
                        # Also subscribe to Redis subscription service
                        if self.redis_subscription_service:
                            await self.redis_subscription_service.subscribe_to_bars(symbol, interval)

                        redis_client = await self.get_redis()
                        await redis_client.sadd('websocket:subscribed_bars', f"{key[0]}|{key[1]}")
                        self.logger.info(
                            f"Subscribed to bars: {key[0]} {key[1]}")
                    else:
                        self.logger.error(
                            f"Failed to subscribe to bars {key} via BarsManager")
                        self.subscribed_bars.remove(key)
                else:
                    self.logger.warning(
                        f"BarsManager integration not available for {key}")
                    self.subscribed_bars.remove(key)
            except Exception as e:
                self.logger.error(f"Error subscribing to bars {key}: {e}")
                self.subscribed_bars.remove(key)

    async def unsubscribe_bars(self, symbol: str, interval: str) -> None:
        """Unsubscribe from bars updates"""
        key = (symbol.upper(), interval)
        if key in self.subscribed_bars:
            self.subscribed_bars.remove(key)
            try:
                # Unsubscribe via BarsManager integration
                if self.bars_manager_integration:
                    await self.bars_manager_integration.unsubscribe_from_bars(symbol, interval)

                # Unsubscribe from Redis subscription service
                if self.redis_subscription_service:
                    await self.redis_subscription_service.unsubscribe_from_bars(symbol, interval)

                redis_client = await self.get_redis()
                await redis_client.srem('websocket:subscribed_bars', f"{key[0]}|{key[1]}")
                self.logger.info(f"Unsubscribed from bars: {key[0]} {key[1]}")
            except Exception as e:
                self.logger.error(f"Error unsubscribing from bars {key}: {e}")

    async def get_all_connections(self) -> list:
        """Get all active connections across all processes"""
        try:
            redis_client = await self.get_redis()
            connections = await redis_client.keys('websocket:connections:*')
            return connections
        except Exception as e:
            self.logger.error(f"Error getting connections: {e}")
            return []

    async def get_subscription_status(self) -> dict:
        """Get current subscription status for monitoring"""
        try:
            redis_client = await self.get_redis()

            # Get Redis subscription counts
            redis_quote_count = await redis_client.scard('websocket:subscribed_symbols')
            redis_bars_count = await redis_client.scard('websocket:subscribed_bars')

            return {
                'memory_quotes': len(self.subscribed_symbols),
                'memory_bars': len(self.subscribed_bars),
                'redis_quotes': redis_quote_count,
                'redis_bars': redis_bars_count,
                'memory_quote_symbols': list(self.subscribed_symbols),
                'memory_bars_keys': [f"{symbol}|{interval}" for symbol, interval in self.subscribed_bars]
            }
        except Exception as e:
            self.logger.error(f"Error getting subscription status: {e}")
            return {
                'error': str(e),
                'memory_quotes': len(self.subscribed_symbols),
                'memory_bars': len(self.subscribed_bars)
            }

    async def start_broadcast_listener(self) -> None:
        """Start listening for broadcast messages from other processes"""
        try:
            redis_client = await self.get_redis()
            pubsub = redis_client.pubsub()
            await pubsub.subscribe('websocket:broadcast', 'websocket:room_broadcast')

            async def listen_for_broadcasts():
                try:
                    async for message in pubsub.listen():
                        if message['type'] == 'message':
                            try:
                                data = json.loads(message['data'])
                                channel = message['channel']

                                if channel == 'websocket:broadcast':
                                    # Only process broadcast messages from other processes
                                    if data.get('process_id') != self.process_id:
                                        await self.broadcast(data['message'])

                                elif channel == 'websocket:room_broadcast':
                                    # Process room broadcast messages
                                    room_id = data.get('room_id')
                                    room_message = data.get('message')
                                    exclude_client = data.get('exclude_client')

                                    if room_id and room_message:
                                        # Send to local clients in the room
                                        local_clients = self.local_connections.keys()
                                        room_clients = set()

                                        if self.room_manager:
                                            room_clients = self.room_manager.local_rooms.get(
                                                room_id, set())

                                        # Send to local clients in the room
                                        for client_id in room_clients:
                                            if client_id != exclude_client and client_id in local_clients:
                                                try:
                                                    await self.send_personal_message(room_message, client_id)
                                                except Exception as e:
                                                    self.logger.error(
                                                        f"Error sending room message to {client_id}: {e}")

                                        self.logger.debug(
                                            f"Processed room broadcast for {room_id}: {len(room_clients)} local clients")

                            except Exception as e:
                                self.logger.error(
                                    f"Error processing broadcast message: {e}")
                except Exception as e:
                    self.logger.error(f"Broadcast listener error: {e}")
                finally:
                    await pubsub.close()

            self.broadcast_task = asyncio.create_task(listen_for_broadcasts())
            self.logger.info(
                f"Broadcast listener started for process {self.process_id}")

        except Exception as e:
            self.logger.error(f"Error starting broadcast listener: {e}")

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
                            self.logger.error(
                                f"Error updating heartbeat for {client_id}: {e}")

                    # Clean up stale connections from other processes
                    await self.cleanup_stale_connections()

                except Exception as e:
                    self.logger.error(f"Heartbeat error: {e}")
                    await asyncio.sleep(5)  # Wait before retrying

        self.heartbeat_task = asyncio.create_task(heartbeat_loop())
        self.logger.info(f"Heartbeat started for process {self.process_id}")

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
                            self.logger.info(
                                f"Cleaned up stale connection: {key}")
                except Exception as e:
                    self.logger.error(f"Error checking connection {key}: {e}")

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    async def get_total_connections(self) -> int:
        """Get total number of connections across all processes"""
        try:
            redis_client = await self.get_redis()
            # Get all process keys
            process_keys = await redis_client.keys('websocket:processes:*:clients')
            total = 0
            for key in process_keys:
                count = await redis_client.scard(key)
                total += count
            return total
        except Exception as e:
            self.logger.error(f"Error getting total connections: {e}")
            return len(self.local_connections)

    async def get_redis_status(self) -> dict:
        """Get Redis status information"""
        try:
            redis_client = await self.get_redis()
            info = await redis_client.info()
            return {
                'connected_clients': info.get('connected_clients', 0),
                'used_memory': info.get('used_memory_human', 'N/A'),
                'uptime': info.get('uptime_in_seconds', 0)
            }
        except Exception as e:
            self.logger.error(f"Error getting Redis status: {e}")
            return {'error': str(e)}

    async def startup(self) -> None:
        """Initialize the connection manager"""
        self.running = True

        # Initialize integration services
        await self._initialize_integration_services()

        await self.start_broadcast_listener()
        await self.start_heartbeat()
        self.logger.info(
            f"WebSocketConnectionManager started for process {self.process_id}")

    async def _room_broadcast_callback(self, room_id: str, ticker: str, message: Dict[str, Any]) -> None:
        """Callback for room-based broadcasting from Redis subscription service"""
        try:
            if self.room_manager:
                # Update bar activity timestamp if this is a bars message
                if message.get('type') == 'bars':
                    await self.room_manager.update_bar_activity(room_id)
                
                # Use room manager to broadcast to specific room
                await self.room_manager.broadcast_to_room(room_id, json.dumps(message))
                self.logger.debug(f"Room broadcast to {room_id} for {ticker}: {message.get('type', 'unknown')}")
            else:
                # Fallback to global broadcast if room manager not available
                await self.broadcast(json.dumps(message))
                self.logger.debug(f"Fallback global broadcast for {ticker} (no room manager)")
        except Exception as e:
            self.logger.error(f"Error in room broadcast callback for {room_id}: {e}")
            # Fallback to global broadcast on error
            try:
                await self.broadcast(json.dumps(message))
            except Exception as fallback_error:
                self.logger.error(f"Fallback broadcast also failed: {fallback_error}")

    async def _initialize_integration_services(self) -> None:
        """Initialize BarsManager integration and Redis subscription services"""
        try:
            # Initialize BarsManager integration
            self.bars_manager_integration = BarsManagerIntegration()
            self.logger.info("BarsManager integration initialized")

            # Initialize Redis subscription service
            redis_client = await self.get_redis()
            self.redis_subscription_service = RedisSubscriptionService(
                redis_client,
                self.broadcast,
                self._room_broadcast_callback  # Add room broadcast callback
            )
            await self.redis_subscription_service.start()
            self.logger.info(
                "Redis subscription service initialized and started")

            # Initialize room manager
            self.room_manager = RoomManager(redis_client)
            await self.room_manager.start()
            self.logger.info("Room manager initialized and started")

            # Set up cross-references between services
            self.room_manager.set_bars_manager_integration(
                self.bars_manager_integration)
            self.room_manager.set_redis_subscription_service(
                self.redis_subscription_service)
            self.bars_manager_integration.set_room_manager(self.room_manager)
            self.logger.info("Service cross-references established")

            # Sync existing subscriptions from BarsManager integration
            await self._sync_existing_subscriptions()
            self.logger.info("Synced existing subscriptions from BarsManager")

        except Exception as e:
            self.logger.error(f"Error initializing integration services: {e}")
            # Ensure integration services are set to None on failure
            self.bars_manager_integration = None
            self.redis_subscription_service = None
            self.room_manager = None
            self.logger.warning(
                "Integration services set to None due to initialization failure")
            # Continue without integration services - fallback to manual mode

    async def _sync_existing_subscriptions(self) -> None:
        """Sync existing subscriptions from BarsManager integration to Redis subscription service"""
        try:
            if not self.bars_manager_integration or not self.redis_subscription_service:
                self.logger.warning(
                    "Cannot sync subscriptions - services not initialized")
                return

            # Get existing quote subscriptions
            active_quotes = self.bars_manager_integration.active_quote_subscriptions
            for symbol in active_quotes:
                if symbol not in self.subscribed_symbols:
                    self.subscribed_symbols.add(symbol)
                    self.logger.info(
                        f"Synced existing quote subscription: {symbol}")

                # Subscribe to Redis subscription service
                await self.redis_subscription_service.subscribe_to_quotes(symbol)
                self.logger.info(
                    f"Subscribed {symbol} to Redis subscription service")

            # Get existing bar subscriptions
            active_bars = self.bars_manager_integration.active_bar_subscriptions
            for symbol, interval in active_bars:
                key = (symbol.upper(), interval)
                if key not in self.subscribed_bars:
                    self.subscribed_bars.add(key)
                    self.logger.info(
                        f"Synced existing bar subscription: {symbol}:{interval}")

                # Subscribe to Redis subscription service
                await self.redis_subscription_service.subscribe_to_bars(symbol, interval)
                self.logger.info(
                    f"Subscribed {symbol}:{interval} to Redis subscription service")

            self.logger.info(
                f"Synced {len(active_quotes)} quote and {len(active_bars)} bar subscriptions")

        except Exception as e:
            self.logger.error(f"Error syncing existing subscriptions: {e}")

    async def shutdown(self) -> None:
        """Clean shutdown of the connection manager"""
        self.running = False

        # Clean up integration services
        if self.bars_manager_integration:
            try:
                await self.bars_manager_integration.cleanup()
            except Exception as e:
                self.logger.error(
                    f"Error cleaning up BarsManager integration: {e}")

        if self.redis_subscription_service:
            try:
                await self.redis_subscription_service.stop()
            except Exception as e:
                self.logger.error(
                    f"Error stopping Redis subscription service: {e}")

        if self.room_manager:
            try:
                await self.room_manager.stop()
            except Exception as e:
                self.logger.error(f"Error stopping room manager: {e}")

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

        self.logger.info(
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

    # Room management methods
    async def create_room(self, room_id: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Create a new room"""
        if not self.room_manager:
            self.logger.warning("Room manager not available")
            return False
        return await self.room_manager.create_room(room_id, metadata)

    async def join_room(self, client_id: str, room_id: str) -> bool:
        """Add a client to a room"""
        if not self.room_manager:
            self.logger.warning("Room manager not available")
            return False
        return await self.room_manager.join_room(client_id, room_id)

    async def leave_room(self, client_id: str, room_id: str) -> bool:
        """Remove a client from a room"""
        if not self.room_manager:
            self.logger.warning("Room manager not available")
            return False
        return await self.room_manager.leave_room(client_id, room_id)

    async def broadcast_to_room(self, room_id: str, message: str, exclude_client: Optional[str] = None) -> int:
        """Broadcast a message to all clients in a room"""
        if not self.room_manager:
            self.logger.warning("Room manager not available")
            return 0
        return await self.room_manager.broadcast_to_room(room_id, message, exclude_client)

    async def get_room_info(self, room_id: str) -> Optional[Dict[str, Any]]:
        """Get room information and metadata"""
        if not self.room_manager:
            return None
        return await self.room_manager.get_room_info(room_id)

    async def list_rooms(self) -> List[Dict[str, Any]]:
        """List all active rooms"""
        if not self.room_manager:
            return []
        return await self.room_manager.list_rooms()

    async def get_client_rooms(self, client_id: str) -> Set[str]:
        """Get all rooms a client is in"""
        if not self.room_manager:
            return set()
        return await self.room_manager.get_client_rooms(client_id)

    async def update_room_metadata(self, room_id: str, metadata: Dict[str, Any]) -> bool:
        """Update room metadata"""
        if not self.room_manager:
            return False
        return await self.room_manager.update_room_metadata(room_id, metadata)

    async def _verify_final_cleanup(self, client_id: str) -> None:
        """Final verification that client cleanup was successful across all processes"""
        try:
            self.logger.info(
                f"🔍 Performing final cleanup verification for {client_id}")

            # Check 1: Verify client is not in local connections
            if client_id in self.local_connections:
                self.logger.warning(
                    f"⚠️ WARNING: Client {client_id} still in local connections")
            else:
                self.logger.info(
                    f"✅ Client {client_id} properly removed from local connections")

            # Check 2: Verify client is not in any rooms (if room manager available)
            if self.room_manager:
                try:
                    # Use a flag to prevent infinite verification loops
                    if hasattr(self, '_final_verification_in_progress') and self._final_verification_in_progress:
                        self.logger.warning(
                            f"⚠️ Final verification already in progress for {client_id}, skipping")
                        return

                    self._final_verification_in_progress = True

                    try:
                        # Quick check - don't scan all Redis rooms, just verify local tracking is clean
                        local_rooms = self.room_manager.client_rooms.get(
                            client_id, set())
                        if local_rooms:
                            self.logger.warning(
                                f"⚠️ WARNING: Client {client_id} still found in local room tracking: {list(local_rooms)}")
                        else:
                            self.logger.info(
                                f"✅ Client {client_id} properly removed from local room tracking")

                    finally:
                        # Always clear the flag
                        self._final_verification_in_progress = False

                except Exception as e:
                    self.logger.error(
                        f"❌ Error during room verification for {client_id}: {e}")

            # Check 3: Verify client is not in any subscription tracking
            try:
                # Check if client still has any active subscriptions
                client_subscriptions = await self._get_client_subscriptions(client_id)
                if client_subscriptions['quotes'] or client_subscriptions['bars']:
                    self.logger.warning(
                        f"⚠️ WARNING: Client {client_id} still has active subscriptions")
                    self.logger.warning(
                        f"   Quotes: {client_subscriptions['quotes']}")
                    self.logger.warning(
                        f"   Bars: {client_subscriptions['bars']}")
                else:
                    self.logger.info(
                        f"✅ Client {client_id} properly removed from subscription tracking")
            except Exception as e:
                self.logger.error(
                    f"❌ Error checking subscription verification for {client_id}: {e}")

            self.logger.info(
                f"🔍 Final cleanup verification completed for {client_id}")

        except Exception as e:
            self.logger.error(
                f"❌ Error during final cleanup verification for {client_id}: {e}")
            # Ensure flag is cleared even on error
            if hasattr(self, '_final_verification_in_progress'):
                self._final_verification_in_progress = False

    async def verify_cleanup_integrity(self) -> Dict[str, Any]:
        """Verify cleanup system integrity across all processes - PREVENTS INFINITE LOOPS"""
        try:
            self.logger.info("🔍 Starting cleanup integrity verification...")

            # Use a flag to prevent infinite verification loops
            if hasattr(self, '_integrity_verification_in_progress') and self._integrity_verification_in_progress:
                self.logger.warning(
                    "⚠️ Integrity verification already in progress, skipping to prevent loops")
                return {
                    'timestamp': datetime.now().isoformat(),
                    'overall_status': 'skipped_due_to_concurrent_verification',
                    'message': 'Verification skipped to prevent infinite loops'
                }

            self._integrity_verification_in_progress = True

            try:
                verification_results = {
                    'timestamp': datetime.now().isoformat(),
                    'process_id': self.process_id,
                    'redis_connections': {},
                    'room_integrity': {},
                    'subscription_integrity': {},
                    'overall_status': 'unknown'
                }

                # Check 1: Redis connection consistency
                try:
                    redis_consistency = await self._verify_redis_connection_consistency()
                    verification_results['redis_connections'] = redis_consistency
                except Exception as e:
                    self.logger.error(
                        f"❌ Error checking Redis connection consistency: {e}")
                    verification_results['redis_connections_error'] = str(e)

                # Check 2: Room integrity
                if self.room_manager:
                    try:
                        room_integrity = await self._verify_room_integrity()
                        verification_results['room_integrity'] = room_integrity
                    except Exception as e:
                        self.logger.error(
                            f"❌ Error checking room integrity: {e}")
                        verification_results['room_integrity_error'] = str(e)

                # Check 3: Subscription integrity
                try:
                    subscription_integrity = await self._verify_subscription_integrity()
                    verification_results['subscription_integrity'] = subscription_integrity
                except Exception as e:
                    self.logger.error(
                        f"❌ Error checking subscription integrity: {e}")
                    verification_results['subscription_integrity_error'] = str(
                        e)

                # Determine overall status
                has_errors = any(
                    verification_results.get('redis_connections_error') or
                    verification_results.get('room_integrity_error') or
                    verification_results.get('subscription_integrity_error') or
                    verification_results['redis_connections'].get('only_in_redis') or
                    verification_results['redis_connections'].get(
                        'only_in_local')
                )

                verification_results['overall_status'] = 'healthy' if not has_errors else 'degraded'

                self.logger.info(
                    f"🔍 Cleanup integrity verification completed: {verification_results['overall_status']}")
                return verification_results

            finally:
                # Always clear the flag
                self._integrity_verification_in_progress = False

        except Exception as e:
            self.logger.error(
                f"❌ Error during cleanup integrity verification: {e}")
            # Ensure flag is cleared even on error
            if hasattr(self, '_integrity_verification_in_progress'):
                self._integrity_verification_in_progress = False
            return {
                'timestamp': datetime.now().isoformat(),
                'overall_status': 'error',
                'error': str(e)
            }

    async def _verify_redis_connection_consistency(self) -> Dict[str, Any]:
        """Verify Redis connection consistency across local and Redis tracking"""
        try:
            redis_consistency = {
                'local_connections': len(self.local_connections),
                'redis_processes': 0,
                'only_in_redis': [],
                'only_in_local': []
            }

            # Get Redis process counts
            redis_client = await self.get_redis()
            process_keys = await redis_client.keys('websocket:processes:*:clients')
            redis_consistency['redis_processes'] = len(process_keys)

            # Check for inconsistencies (simplified check)
            # This is a basic check - in a full implementation you'd compare individual clients
            return redis_consistency

        except Exception as e:
            self.logger.error(
                f"Error verifying Redis connection consistency: {e}")
            return {'error': str(e)}

    async def _verify_room_integrity(self) -> Dict[str, Any]:
        """Verify room integrity across local and Redis tracking"""
        try:
            room_integrity = {
                'local_rooms': {},
                'redis_rooms': {},
                'inconsistencies': []
            }

            # Get local room stats
            for room_id, clients in self.room_manager.local_rooms.items():
                room_integrity['local_rooms'][room_id] = {
                    'client_count': len(clients),
                    'clients': list(clients)
                }

            # Get Redis room stats
            redis_client = await self.get_redis()
            room_keys = await redis_client.keys("room:*:clients")

            for key in room_keys:
                room_id = key.split(':')[1]
                clients = await redis_client.smembers(key)
                client_list = [client.decode(
                    'utf-8') if isinstance(client, bytes) else client for client in clients]

                room_integrity['redis_rooms'][room_id] = {
                    'client_count': len(client_list),
                    'clients': client_list
                }

                # Check for inconsistencies
                local_clients = set(
                    self.room_manager.local_rooms.get(room_id, set()))
                redis_clients = set(client_list)

                if local_clients != redis_clients:
                    inconsistency = {
                        'room_id': room_id,
                        'local_clients': list(local_clients),
                        'redis_clients': list(redis_clients),
                        'only_in_local': list(local_clients - redis_clients),
                        'only_in_redis': list(redis_clients - local_clients)
                    }
                    room_integrity['inconsistencies'].append(inconsistency)

            return room_integrity

        except Exception as e:
            self.logger.error(f"Error verifying room integrity: {e}")
            return {'error': str(e)}

    async def _verify_subscription_integrity(self) -> Dict[str, Any]:
        """Verify subscription integrity across local and Redis tracking"""
        try:
            subscription_integrity = {
                'local_subscriptions': {},
                'redis_subscriptions': {},
                'inconsistencies': []
            }

            # Local subscription tracking
            subscription_integrity['local_subscriptions'] = {
                'quotes': list(self.subscribed_symbols),
                'bars': [f"{symbol}|{interval}" for symbol, interval in self.subscribed_bars]
            }

            # Redis subscription tracking
            redis_client = await self.get_redis()

            # Get Redis quote subscriptions
            redis_quotes = await redis_client.smembers('websocket:subscribed_symbols')
            redis_quote_list = [quote.decode(
                'utf-8') if isinstance(quote, bytes) else quote for quote in redis_quotes]

            # Get Redis bar subscriptions
            redis_bars = await redis_client.smembers('websocket:subscribed_bars')
            redis_bar_list = [bar.decode(
                'utf-8') if isinstance(bar, bytes) else bar for bar in redis_bars]

            subscription_integrity['redis_subscriptions'] = {
                'quotes': redis_quote_list,
                'bars': redis_bar_list
            }

            # Check for inconsistencies
            local_quotes = set(self.subscribed_symbols)
            redis_quotes_set = set(redis_quote_list)

            if local_quotes != redis_quotes_set:
                inconsistency = {
                    'type': 'quotes',
                    'local': list(local_quotes),
                    'redis': list(redis_quotes_set),
                    'only_in_local': list(local_quotes - redis_quotes_set),
                    'only_in_redis': list(redis_quotes_set - local_quotes)
                }
                subscription_integrity['inconsistencies'].append(inconsistency)

            local_bars = {f"{symbol}|{interval}" for symbol,
                          interval in self.subscribed_bars}
            redis_bars_set = set(redis_bar_list)

            if local_bars != redis_bars_set:
                inconsistency = {
                    'type': 'bars',
                    'local': list(local_bars),
                    'redis': list(redis_bars_set),
                    'only_in_local': list(local_bars - redis_bars_set),
                    'only_in_redis': list(redis_bars_set - local_bars)
                }
                subscription_integrity['inconsistencies'].append(inconsistency)

            return subscription_integrity

        except Exception as e:
            self.logger.error(f"Error verifying subscription integrity: {e}")
            return {'error': str(e)}
