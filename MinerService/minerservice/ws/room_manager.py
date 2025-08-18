"""Room management for WebSocket connections in distributed environments"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import redis.asyncio as redis
from detonator import get_logger


class RoomManager:
    """Manages WebSocket rooms across multiple processes using Redis"""

    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.logger = get_logger('RoomManager', logging.DEBUG)
        self.process_id = str(uuid.uuid4())

        # Local room tracking for this process
        # room_id -> set of client_ids
        self.local_rooms: Dict[str, Set[str]] = {}
        # client_id -> set of room_ids
        self.client_rooms: Dict[str, Set[str]] = {}

        # Room metadata
        self.room_metadata: Dict[str, Dict[str, Any]] = {}

        # Data subscription tracking
        self.quote_rooms: Dict[str, str] = {}  # ticker -> room_id
        # (ticker, interval) -> room_id
        self.bar_rooms: Dict[Tuple[str, str], str] = {}

        # BarsManager integration reference
        self.bars_manager_integration = None

        # Background tasks
        self.cleanup_task: Optional[asyncio.Task] = None
        self.data_broadcast_task: Optional[asyncio.Task] = None
        self.running = False

    async def start(self) -> None:
        """Start the room manager"""
        self.running = True
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        self.data_broadcast_task = asyncio.create_task(
            self._data_broadcast_loop())
        self.logger.info(f"RoomManager started for process {self.process_id}")

    def set_bars_manager_integration(self, bars_manager_integration) -> None:
        """Set the BarsManager integration reference"""
        self.bars_manager_integration = bars_manager_integration
        self.logger.info("BarsManager integration set for RoomManager")

    async def manual_cleanup_empty_rooms(self) -> Dict[str, Any]:
        """Manually trigger cleanup of empty rooms and return cleanup results"""
        try:
            self.logger.info("Manual cleanup of empty rooms triggered")

            # Get all rooms
            rooms = await self.list_rooms()
            cleanup_results: Dict[str, Any] = {
                'total_rooms': len(rooms),
                'empty_rooms_found': 0,
                'rooms_cleaned': 0,
                'bars_manager_unsubscriptions': 0,
                'errors': []
            }

            for room in rooms:
                try:
                    room_id = room['room_id']
                    client_count = room['client_count']

                    if client_count == 0:
                        cleanup_results['empty_rooms_found'] += 1
                        self.logger.info(
                            f"Manual cleanup: Found empty room {room_id}")

                        # Clean up the empty room
                        await self._check_and_cleanup_empty_room(room_id)
                        cleanup_results['rooms_cleaned'] += 1

                        # Count BarsManager unsubscriptions
                        room_metadata = self.room_metadata.get(room_id, {})
                        if room_metadata.get('type') in ['quote', 'bars']:
                            cleanup_results['bars_manager_unsubscriptions'] += 1

                except Exception as e:
                    error_msg = f"Error cleaning up room {room['room_id']}: {e}"
                    self.logger.error(error_msg)
                    cleanup_results['errors'].append(error_msg)

            self.logger.info(f"Manual cleanup completed: {cleanup_results}")
            return cleanup_results

        except Exception as e:
            error_msg = f"Error in manual cleanup: {e}"
            self.logger.error(error_msg)
            return {
                'total_rooms': 0,
                'empty_rooms_found': 0,
                'rooms_cleaned': 0,
                'bars_manager_unsubscriptions': 0,
                'errors': [error_msg]
            }

    async def stop(self) -> None:
        """Stop the room manager"""
        self.running = False
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        if self.data_broadcast_task:
            self.data_broadcast_task.cancel()
            try:
                await self.data_broadcast_task
            except asyncio.CancelledError:
                pass
        self.logger.info(f"RoomManager stopped for process {self.process_id}")

    async def create_quote_room(self, ticker: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create a room for quote subscriptions"""
        room_id = f"quotes:{ticker.upper()}"

        # Check if room already exists
        if room_id in self.quote_rooms:
            return room_id

        # Create room with quote-specific metadata
        room_metadata = {
            'type': 'quote',
            'ticker': ticker.upper(),
            'subscription_type': 'quotes',
            **(metadata or {})
        }

        success = await self.create_room(room_id, room_metadata)
        if success:
            self.quote_rooms[ticker.upper()] = room_id
            self.logger.info(f"Created quote room: {room_id} for {ticker}")
            return room_id
        else:
            raise Exception(f"Failed to create quote room for {ticker}")

    async def create_bar_room(self, ticker: str, interval: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create a room for bar subscriptions"""
        room_id = f"bars:{ticker.upper()}:{interval}"

        # Check if room already exists
        subscription_key = (ticker.upper(), interval)
        if subscription_key in self.bar_rooms:
            return room_id

        # Create room with bar-specific metadata
        room_metadata = {
            'type': 'bars',
            'ticker': ticker.upper(),
            'interval': interval,
            'subscription_type': 'bars',
            **(metadata or {})
        }

        success = await self.create_room(room_id, room_metadata)
        if success:
            self.bar_rooms[subscription_key] = room_id
            self.logger.info(
                f"Created bar room: {room_id} for {ticker} {interval}")
            return room_id
        else:
            raise Exception(
                f"Failed to create bar room for {ticker} {interval}")

    async def subscribe_to_quotes(self, ticker: str) -> str:
        """Subscribe to quotes and create/join quote room"""
        try:
            # Create quote room if it doesn't exist
            room_id = await self.create_quote_room(ticker)

            # Subscribe to BarsManager if integration is available
            if self.bars_manager_integration:
                await self.bars_manager_integration.subscribe_to_quotes(ticker)
                self.logger.info(
                    f"Subscribed to quotes for {ticker} via BarsManager")

            return room_id

        except Exception as e:
            self.logger.error(
                f"Failed to subscribe to quotes for {ticker}: {e}")
            raise

    async def subscribe_to_bars(self, ticker: str, interval: str) -> str:
        """Subscribe to bars and create/join bar room"""
        try:
            # Create bar room if it doesn't exist
            room_id = await self.create_bar_room(ticker, interval)

            # Subscribe to BarsManager if integration is available
            if self.bars_manager_integration:
                await self.bars_manager_integration.subscribe_to_bars(ticker, interval)
                self.logger.info(
                    f"Subscribed to bars for {ticker} {interval} via BarsManager")

            return room_id

        except Exception as e:
            self.logger.error(
                f"Failed to subscribe to bars for {ticker} {interval}: {e}")
            raise

    async def unsubscribe_from_quotes(self, ticker: str) -> bool:
        """Unsubscribe from quotes and clean up quote room"""
        try:
            room_id = self.quote_rooms.get(ticker.upper())
            if not room_id:
                return True

            # Unsubscribe from BarsManager if integration is available
            if self.bars_manager_integration:
                await self.bars_manager_integration.unsubscribe_from_quotes(ticker)
                self.logger.info(
                    f"Unsubscribed from quotes for {ticker} via BarsManager")

            # Remove from tracking
            self.quote_rooms.pop(ticker.upper(), None)

            # Check if room is empty and delete if so
            room_clients = await self.get_room_clients(room_id)
            if not room_clients:
                await self.delete_room(room_id)
                self.logger.info(f"Deleted empty quote room: {room_id}")

            return True

        except Exception as e:
            self.logger.error(
                f"Failed to unsubscribe from quotes for {ticker}: {e}")
            return False

    async def unsubscribe_from_bars(self, ticker: str, interval: str) -> bool:
        """Unsubscribe from bars and clean up bar room"""
        try:
            subscription_key = (ticker.upper(), interval)
            room_id = self.bar_rooms.get(subscription_key)
            if not room_id:
                return True

            # Unsubscribe from BarsManager if integration is available
            if self.bars_manager_integration:
                await self.bars_manager_integration.unsubscribe_from_bars(ticker, interval)
                self.logger.info(
                    f"Unsubscribed from bars for {ticker} {interval} via BarsManager")

            # Remove from tracking
            self.bar_rooms.pop(subscription_key, None)

            # Check if room is empty and delete if so
            room_clients = await self.get_room_clients(room_id)
            if not room_clients:
                await self.delete_room(room_id)
                self.logger.info(f"Deleted empty bar room: {room_id}")

            return True

        except Exception as e:
            self.logger.error(
                f"Failed to unsubscribe from bars for {ticker} {interval}: {e}")
            return False

    async def create_room(self, room_id: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Create a new room"""
        try:
            # Convert metadata to string representation for Redis storage
            metadata_str = json.dumps(metadata) if metadata else "{}"

            room_data = {
                'room_id': room_id,
                'created_at': datetime.now().isoformat(),
                'created_by': self.process_id,
                'metadata': metadata_str,
                'last_activity': datetime.now().isoformat()
            }

            # Store room info in Redis
            await self.redis_client.hset(f"room:{room_id}", mapping=room_data)
            # 24 hour TTL
            await self.redis_client.expire(f"room:{room_id}", 86400)

            # Add to local tracking
            self.local_rooms[room_id] = set()
            self.room_metadata[room_id] = metadata or {}

            self.logger.info(f"Created room: {room_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to create room {room_id}: {e}")
            return False

    async def delete_room(self, room_id: str) -> bool:
        """Delete a room and remove all clients"""
        try:
            # Get all clients in the room
            clients = await self.get_room_clients(room_id)

            # Remove all clients from the room
            for client_id in clients:
                await self.leave_room(client_id, room_id)

            # Remove room from Redis
            await self.redis_client.delete(f"room:{room_id}")
            await self.redis_client.delete(f"room:{room_id}:clients")

            # Remove from local tracking
            self.local_rooms.pop(room_id, None)
            self.room_metadata.pop(room_id, None)

            self.logger.info(f"Deleted room: {room_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to delete room {room_id}: {e}")
            return False

    async def join_room(self, client_id: str, room_id: str) -> bool:
        """Add a client to a room"""
        try:
            # Check if room exists
            room_exists = await self.redis_client.exists(f"room:{room_id}")
            if not room_exists:
                # Create room if it doesn't exist
                await self.create_room(room_id)

            # Add client to room in Redis
            await self.redis_client.sadd(f"room:{room_id}:clients", client_id)
            await self.redis_client.expire(f"room:{room_id}:clients", 86400)

            # Add client to room in local tracking
            if room_id not in self.local_rooms:
                self.local_rooms[room_id] = set()
            self.local_rooms[room_id].add(client_id)

            # Track which rooms the client is in
            if client_id not in self.client_rooms:
                self.client_rooms[client_id] = set()
            self.client_rooms[client_id].add(room_id)

            # Update room activity
            await self.redis_client.hset(f"room:{room_id}", 'last_activity', datetime.now().isoformat())

            self.logger.info(f"Client {client_id} joined room {room_id}")
            return True

        except Exception as e:
            self.logger.error(
                f"Failed to join room {room_id} for client {client_id}: {e}")
            return False

    async def leave_room(self, client_id: str, room_id: str) -> bool:
        """Remove a client from a room"""
        try:
            self.logger.info(
                f"🚪 leave_room called for client {client_id} in room {room_id}")

            # Remove client from room in Redis
            await self.redis_client.srem(f"room:{room_id}:clients", client_id)
            self.logger.info(
                f"🗑️ Removed client {client_id} from Redis room {room_id}")

            # Remove from local tracking
            if room_id in self.local_rooms:
                self.local_rooms[room_id].discard(client_id)
                self.logger.info(
                    f"🗑️ Removed client {client_id} from local room {room_id}")

            if client_id in self.client_rooms:
                self.client_rooms[client_id].discard(room_id)
                self.logger.info(
                    f"🗑️ Removed room {room_id} from client {client_id}")

            # Update room activity
            await self.redis_client.hset(f"room:{room_id}", 'last_activity', datetime.now().isoformat())
            self.logger.info(f"🕒 Updated last activity for room {room_id}")

            self.logger.info(f"✅ Client {client_id} left room {room_id}")

            # Check if room is now empty and clean up if needed
            self.logger.info(f"🔍 Checking if room {room_id} is now empty...")
            await self._check_and_cleanup_empty_room(room_id)

            return True

        except Exception as e:
            self.logger.error(
                f"❌ Failed to leave room {room_id} for client {client_id}: {e}")
            import traceback
            self.logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return False

    async def _check_and_cleanup_empty_room(self, room_id: str) -> None:
        """Check if a room is empty and clean it up if so, including BarsManager unsubscription"""
        try:
            # Get total client count across all processes
            total_clients = await self.get_room_clients(room_id)
            self.logger.info(
                f"🔍 Checking room {room_id} - total clients: {len(total_clients)}")

            if not total_clients:
                self.logger.info(f"🚪 Room {room_id} is empty, cleaning up...")

                # Debug: Check what metadata we have
                self.logger.info(
                    f"🔍 Room metadata for {room_id}: {self.room_metadata.get(room_id, 'NOT_FOUND')}")
                self.logger.info(
                    f"🔍 All room metadata keys: {list(self.room_metadata.keys())}")

                # Determine room type and ticker/interval for BarsManager unsubscription
                room_metadata = self.room_metadata.get(room_id, {})
                room_type = room_metadata.get('type')
                self.logger.info(
                    f"🔍 Room type: {room_type}, metadata: {room_metadata}")

                if room_type == 'quote':
                    ticker = room_metadata.get('ticker')
                    self.logger.info(
                        f"🔍 Quote room cleanup for ticker: {ticker}")
                    if ticker and self.bars_manager_integration:
                        try:
                            self.logger.info(
                                f"🔌 Unsubscribing from BarsManager quotes for {ticker}")
                            await self.bars_manager_integration.unsubscribe_from_quotes(ticker)
                            self.logger.info(
                                f"✅ Unsubscribed from quotes for {ticker} via BarsManager (room empty)")
                        except Exception as e:
                            self.logger.error(
                                f"❌ Failed to unsubscribe from quotes for {ticker}: {e}")
                    else:
                        self.logger.warning(
                            f"⚠️ Cannot unsubscribe: ticker={ticker}, bars_manager_integration={self.bars_manager_integration}")

                    # Remove from quote rooms tracking
                    if ticker in self.quote_rooms:
                        self.quote_rooms.pop(ticker, None)
                        self.logger.info(
                            f"🗑️ Removed {ticker} from quote rooms tracking")
                    else:
                        self.logger.warning(
                            f"⚠️ {ticker} not found in quote_rooms tracking")

                elif room_type == 'bars':
                    ticker = room_metadata.get('ticker')
                    interval = room_metadata.get('interval')
                    self.logger.info(
                        f"🔍 Bars room cleanup for ticker: {ticker}, interval: {interval}")
                    if ticker and interval and self.bars_manager_integration:
                        try:
                            self.logger.info(
                                f"🔌 Unsubscribing from BarsManager bars for {ticker} {interval}")
                            await self.bars_manager_integration.unsubscribe_from_bars(ticker, interval)
                            self.logger.info(
                                f"✅ Unsubscribed from bars for {ticker} {interval} via BarsManager (room empty)")
                        except Exception as e:
                            self.logger.error(
                                f"❌ Failed to unsubscribe from bars for {ticker} {interval}: {e}")
                    else:
                        self.logger.warning(
                            f"⚠️ Cannot unsubscribe: ticker={ticker}, interval={interval}, bars_manager_integration={self.bars_manager_integration}")

                    # Remove from bar rooms tracking
                    subscription_key = (ticker, interval)
                    if subscription_key in self.bar_rooms:
                        self.bar_rooms.pop(subscription_key, None)
                        self.logger.info(
                            f"🗑️ Removed {ticker}:{interval} from bar rooms tracking")
                    else:
                        self.logger.warning(
                            f"⚠️ {subscription_key} not found in bar_rooms tracking")

                else:
                    self.logger.warning(
                        f"⚠️ Unknown room type: {room_type} for room {room_id}")

                # Delete the empty room
                self.logger.info(f"🗑️ Deleting empty room: {room_id}")
                await self.delete_room(room_id)
                self.logger.info(f"✅ Deleted empty room: {room_id}")
            else:
                self.logger.info(
                    f"✅ Room {room_id} still has {len(total_clients)} clients, skipping cleanup")

        except Exception as e:
            self.logger.error(
                f"❌ Error checking and cleaning up empty room {room_id}: {e}")
            import traceback
            self.logger.error(f"❌ Traceback: {traceback.format_exc()}")

    async def get_room_clients(self, room_id: str) -> Set[str]:
        """Get all clients in a room across all processes"""
        try:
            clients = await self.redis_client.smembers(f"room:{room_id}:clients")
            return {client.decode('utf-8') if isinstance(client, bytes) else client for client in clients}
        except Exception as e:
            self.logger.error(f"Failed to get clients for room {room_id}: {e}")
            return set()

    async def get_client_rooms(self, client_id: str) -> Set[str]:
        """Get all rooms a client is in"""
        try:
            # Check local tracking first
            local_rooms = self.client_rooms.get(client_id, set())

            # Also check Redis for rooms from other processes
            redis_rooms = set()
            room_keys = await self.redis_client.keys("room:*:clients")
            for key in room_keys:
                room_id = key.split(':')[1]
                is_member = await self.redis_client.sismember(key, client_id)
                if is_member:
                    redis_rooms.add(room_id)

            # Combine local and Redis rooms
            all_rooms = local_rooms.union(redis_rooms)

            # Update local tracking
            self.client_rooms[client_id] = all_rooms

            return all_rooms

        except Exception as e:
            self.logger.error(
                f"Failed to get rooms for client {client_id}: {e}")
            return self.client_rooms.get(client_id, set())

    async def broadcast_to_room(self, room_id: str, message: str, exclude_client: Optional[str] = None) -> int:
        """Broadcast a message to all clients in a room"""
        try:
            clients = await self.get_room_clients(room_id)
            if exclude_client:
                clients.discard(exclude_client)

            # Store message in Redis for other processes to pick up
            broadcast_data = {
                'type': 'room_broadcast',
                'room_id': room_id,
                'message': message,
                'exclude_client': exclude_client,
                'process_id': self.process_id,
                'timestamp': datetime.now().isoformat()
            }

            await self.redis_client.publish('websocket:room_broadcast', json.dumps(broadcast_data))

            # Send to local clients
            local_clients = self.local_rooms.get(room_id, set())
            local_count = len(local_clients)

            self.logger.info(
                f"Broadcasting to room {room_id}: {local_count} local clients, {len(clients)} total clients")
            return local_count

        except Exception as e:
            self.logger.error(f"Failed to broadcast to room {room_id}: {e}")
            return 0

    async def get_room_info(self, room_id: str) -> Optional[Dict[str, Any]]:
        """Get room information and metadata"""
        try:
            room_data = await self.redis_client.hgetall(f"room:{room_id}")
            if not room_data:
                return None

            # Get client count
            client_count = await self.redis_client.scard(f"room:{room_id}:clients")

            room_info = {
                'room_id': room_id,
                'client_count': client_count,
                'created_at': room_data.get('created_at'),
                'created_by': room_data.get('created_by'),
                'last_activity': room_data.get('last_activity'),
                'metadata': json.loads(room_data.get('metadata', '{}'))
            }

            return room_info

        except Exception as e:
            self.logger.error(f"Failed to get room info for {room_id}: {e}")
            return None

    async def list_rooms(self) -> List[Dict[str, Any]]:
        """List all active rooms"""
        try:
            room_keys = await self.redis_client.keys("room:*")
            rooms = []

            for key in room_keys:
                room_id = key.split(':')[1]
                room_info = await self.get_room_info(room_id)
                if room_info:
                    rooms.append(room_info)

            return sorted(rooms, key=lambda x: x['last_activity'], reverse=True)

        except Exception as e:
            self.logger.error(f"Failed to list rooms: {e}")
            return []

    async def update_room_metadata(self, room_id: str, metadata: Dict[str, Any]) -> bool:
        """Update room metadata"""
        try:
            # Update in Redis
            await self.redis_client.hset(f"room:{room_id}", 'metadata', json.dumps(metadata))
            await self.redis_client.hset(f"room:{room_id}", 'last_activity', datetime.now().isoformat())

            # Update local tracking
            self.room_metadata[room_id] = metadata

            self.logger.info(f"Updated metadata for room {room_id}")
            return True

        except Exception as e:
            self.logger.error(
                f"Failed to update metadata for room {room_id}: {e}")
            return False

    async def cleanup_client(self, client_id: str) -> None:
        """Clean up when a client disconnects"""
        try:
            print(f"Starting room cleanup for client: {client_id}")

            # Step 1: Get all rooms the client was in
            client_rooms = self.client_rooms.get(client_id, set()).copy()
            print(
                f"Client {client_id} was in {len(client_rooms)} rooms: {list(client_rooms)}")

            # Step 2: Remove client from all rooms
            for room_id in client_rooms:
                try:
                    await self.leave_room(client_id, room_id)
                    print(f"Removed {client_id} from room {room_id}")
                except Exception as e:
                    print(
                        f"Error removing {client_id} from room {room_id}: {e}")

            # Step 3: Clean up local tracking
            self.client_rooms.pop(client_id, None)

            # Step 4: Clean up any empty rooms
            await self._cleanup_empty_rooms()

            print(
                f"✅ Room cleanup completed for client {client_id} from {len(client_rooms)} rooms")

        except Exception as e:
            print(f"❌ Failed to cleanup client {client_id}: {e}")
            # Try to at least clean up local tracking
            try:
                self.client_rooms.pop(client_id, None)
            except:
                pass

    async def _cleanup_empty_rooms(self) -> None:
        """Clean up rooms that have no clients, including BarsManager unsubscription"""
        try:
            empty_rooms = []

            # Check local rooms for empty ones
            for room_id, clients in self.local_rooms.items():
                if not clients:
                    empty_rooms.append(room_id)
                    print(f"Found empty local room: {room_id}")

            # Clean up empty rooms
            for room_id in empty_rooms:
                try:
                    # Check if room is actually empty across all processes
                    redis_client_count = await self.get_room_clients(room_id)
                    if not redis_client_count:
                        # Room is empty across all processes, clean it up
                        await self._check_and_cleanup_empty_room(room_id)
                    else:
                        print(
                            f"Room {room_id} has {len(redis_client_count)} clients in other processes")

                except Exception as e:
                    print(f"Error cleaning up empty room {room_id}: {e}")

        except Exception as e:
            print(f"Error in empty room cleanup: {e}")

    async def _cleanup_loop(self) -> None:
        """Background task to clean up stale rooms and ensure BarsManager unsubscription"""
        while self.running:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes

                # Get all rooms
                rooms = await self.list_rooms()
                current_time = datetime.now()

                for room in rooms:
                    try:
                        room_id = room['room_id']
                        client_count = room['client_count']

                        # Check if room is empty
                        if client_count == 0:
                            self.logger.info(
                                f"Found empty room in cleanup loop: {room_id}")
                            await self._check_and_cleanup_empty_room(room_id)
                            continue

                        # Check if room is stale (no activity for 1 hour)
                        last_activity = datetime.fromisoformat(
                            room['last_activity'])
                        if (current_time - last_activity).total_seconds() > 3600:
                            # Room is stale, check if it's empty
                            if client_count == 0:
                                await self._check_and_cleanup_empty_room(room_id)
                                self.logger.info(
                                    f"Deleted stale empty room: {room_id}")
                            else:
                                # Room has clients but is stale, log for monitoring
                                self.logger.warning(
                                    f"Room {room_id} is stale but has {client_count} clients")

                    except Exception as e:
                        self.logger.error(
                            f"Error checking room {room['room_id']}: {e}")

            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(60)  # Wait before retrying

    def get_local_room_stats(self) -> Dict[str, Any]:
        """Get local room statistics for monitoring"""
        return {
            'local_rooms': len(self.local_rooms),
            'local_clients': len(self.client_rooms),
            'quote_rooms': len(self.quote_rooms),
            'bar_rooms': len(self.bar_rooms),
            'room_details': {
                room_id: {
                    'client_count': len(clients),
                    'metadata': self.room_metadata.get(room_id, {})
                }
                for room_id, clients in self.local_rooms.items()
            }
        }

    async def _data_broadcast_loop(self) -> None:
        """Background task to broadcast market data to rooms"""
        while self.running:
            try:
                await asyncio.sleep(1)  # Check every second for new data

                if not self.bars_manager_integration:
                    continue

                # Broadcast quotes to quote rooms
                for ticker, room_id in self.quote_rooms.items():
                    try:
                        # Get latest quote data
                        quote_data = await self.bars_manager_integration.get_initial_quote(ticker)
                        if quote_data and quote_data.get('status') != 'subscribed_waiting_for_data':
                            # Broadcast quote to room
                            message = json.dumps({
                                'type': 'quote_update',
                                'data': quote_data,
                                'timestamp': datetime.now().isoformat()
                            })
                            await self.broadcast_to_room(room_id, message)
                    except Exception as e:
                        self.logger.error(
                            f"Error broadcasting quote for {ticker}: {e}")

                # Broadcast bars to bar rooms (less frequent)
                if int(datetime.now().timestamp()) % 5 == 0:  # Every 5 seconds
                    for (ticker, interval), room_id in self.bar_rooms.items():
                        try:
                            # Get latest bars data
                            bars_data = await self.bars_manager_integration.get_initial_bars_snapshot(ticker, interval)
                            if bars_data and len(bars_data) > 0:
                                # Get only the latest bar
                                latest_bar = bars_data[-1]
                                message = json.dumps({
                                    'type': 'bar_update',
                                    'data': {
                                        'symbol': ticker,
                                        'interval': interval,
                                        'bar': latest_bar
                                    },
                                    'timestamp': datetime.now().isoformat()
                                })
                                await self.broadcast_to_room(room_id, message)
                        except Exception as e:
                            self.logger.error(
                                f"Error broadcasting bar for {ticker} {interval}: {e}")

            except Exception as e:
                self.logger.error(f"Error in data broadcast loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying
