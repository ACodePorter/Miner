"""Redis subscription service for consuming BarsManager published data"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional

import redis.asyncio as redis
from detonator import get_logger


class RedisSubscriptionService:
    """Service to subscribe to BarsManager's Redis channels and forward data to WebSocket clients"""

    def __init__(self, redis_client: redis.Redis, broadcast_callback: Callable[[str], Awaitable[None]], room_broadcast_callback: Optional[Callable[[str, str, Dict[str, Any]], Awaitable[None]]] = None):
        self.redis_client = redis_client
        self.broadcast_callback = broadcast_callback
        self.room_broadcast_callback = room_broadcast_callback  # New callback for room-based broadcasting
        self.logger = get_logger('RedisSubscriptionService', logging.DEBUG)
        self.running = False
        self.pubsub: Optional[redis.client.PubSub] = None
        self.subscription_task: Optional[asyncio.Task[None]] = None

        # Track active subscriptions
        self.active_quote_subscriptions: set[str] = set()
        # (ticker, interval)
        self.active_bar_subscriptions: set[tuple[str, str]] = set()

    async def start(self) -> None:
        """Start the Redis subscription service"""
        if self.running:
            self.logger.info("Service already running")
            return

        self.running = True
        self.logger.info("Starting Redis subscription service")

        # Start subscription task
        self.subscription_task = asyncio.create_task(
            self._run_subscription_loop())

        # Wait a moment to ensure the task starts
        await asyncio.sleep(0.5)

        # Check if task is running
        if self.subscription_task.done():
            try:
                await self.subscription_task
            except Exception as e:
                self.logger.error(f"Subscription task failed to start: {e}")
                self.running = False
                raise
        else:
            self.logger.info("Subscription task started successfully")

        # Ensure all active subscriptions are properly subscribed to Redis channels
        await self._ensure_all_subscriptions_active()

    async def stop(self) -> None:
        """Stop the Redis subscription service"""
        if not self.running:
            return

        self.running = False
        self.logger.info("Stopping Redis subscription service")

        # Cancel subscription task
        if self.subscription_task:
            self.subscription_task.cancel()
            try:
                await self.subscription_task
            except asyncio.CancelledError:
                pass
            self.subscription_task = None

        # Close pubsub connection
        if self.pubsub:
            await self.pubsub.close()
            self.pubsub = None

    async def subscribe_to_quotes(self, ticker: str) -> None:
        """Subscribe to quotes for a specific ticker"""
        if ticker not in self.active_quote_subscriptions:
            self.active_quote_subscriptions.add(ticker)
            self.logger.info(f"Subscribed to quotes for {ticker}")

            # Subscribe to Redis channel if pubsub is already running
            if self.pubsub and self.running:
                try:
                    await self.pubsub.subscribe(f"quotes:{ticker}")
                    self.logger.info(
                        f"Added Redis subscription to quotes:{ticker}")
                except Exception as e:
                    self.logger.error(
                        f"Failed to subscribe to quotes:{ticker}: {e}")
            else:
                self.logger.info(
                    f"Queued quote subscription for {ticker} (pubsub not ready)")
                self.logger.info(
                    f"PubSub status: pubsub={self.pubsub is not None}, running={self.running}")
        else:
            self.logger.info(f"Already subscribed to quotes for {ticker}")

        # Log current state
        self.logger.info(
            f"Current active quote subscriptions: {list(self.active_quote_subscriptions)}")
        self.logger.info(
            f"PubSub ready: {self.pubsub is not None}, Service running: {self.running}")

        # If pubsub is not ready, try to refresh subscriptions when it becomes available
        if not self.pubsub or not self.running:
            self.logger.info(
                f"Service not ready, will refresh subscriptions when available")
            # Schedule a refresh attempt
            asyncio.create_task(self._refresh_when_ready())
        else:
            # Service is ready, ensure the new subscription is active
            self.logger.info(
                f"Service is ready, ensuring new subscription is active")
            await self._ensure_all_subscriptions_active()

            # If this is the first subscription, remove dummy subscription
            if len(self.active_quote_subscriptions) == 1 and len(self.active_bar_subscriptions) == 0:
                try:
                    await self.pubsub.unsubscribe('__dummy__')
                    self.logger.info(
                        "Removed dummy subscription as we now have real subscriptions")
                except Exception as e:
                    self.logger.warning(
                        f"Failed to remove dummy subscription: {e}")

    async def unsubscribe_from_quotes(self, ticker: str) -> None:
        """Unsubscribe from quotes for a specific ticker"""
        if ticker in self.active_quote_subscriptions:
            self.active_quote_subscriptions.remove(ticker)
            self.logger.info(f"Unsubscribed from quotes for {ticker}")

            # Unsubscribe from Redis channel if pubsub is running
            if self.pubsub and self.running:
                await self.pubsub.unsubscribe(f"quotes:{ticker}")
                self.logger.info(
                    f"Removed Redis subscription from quotes:{ticker}")
            else:
                self.logger.info(
                    f"Queued quote unsubscription for {ticker} (pubsub not ready)")
        else:
            self.logger.info(f"Already unsubscribed from quotes for {ticker}")

    async def subscribe_to_bars(self, ticker: str, interval: str) -> None:
        """Subscribe to bars for a specific ticker and interval"""
        subscription_key = (ticker, interval)
        if subscription_key not in self.active_bar_subscriptions:
            self.active_bar_subscriptions.add(subscription_key)
            self.logger.info(f"Subscribed to {interval} bars for {ticker}")

            # Subscribe to Redis channel if pubsub is already running
            if self.pubsub and self.running:
                await self.pubsub.subscribe(f"bars:{ticker}:{interval}")
                self.logger.info(
                    f"Added Redis subscription to bars:{ticker}:{interval}")
            else:
                self.logger.info(
                    f"Queued bar subscription for {ticker} {interval} (pubsub not ready)")
                self.logger.info(
                    f"PubSub status: pubsub={self.pubsub is not None}, running={self.running}")
        else:
            self.logger.info(
                f"Already subscribed to {interval} bars for {ticker}")

    async def unsubscribe_from_bars(self, ticker: str, interval: str) -> None:
        """Unsubscribe from bars for a specific ticker and interval"""
        subscription_key = (ticker, interval)
        if subscription_key in self.active_bar_subscriptions:
            self.active_bar_subscriptions.remove(subscription_key)
            self.logger.info(f"Unsubscribed from {interval} bars for {ticker}")

            # Unsubscribe from Redis channel if pubsub is running
            if self.pubsub and self.running:
                await self.pubsub.unsubscribe(f"bars:{ticker}:{interval}")
                self.logger.info(
                    f"Removed Redis subscription from bars:{ticker}:{interval}")
            else:
                self.logger.info(
                    f"Queued bar unsubscription for {ticker} {interval} (pubsub not ready)")
        else:
            self.logger.info(
                f"Already unsubscribed from {interval} bars for {ticker}")

    async def _run_subscription_loop(self) -> None:
        """Main subscription loop that listens to Redis channels"""
        try:
            self.logger.info("Starting subscription loop...")

            # Create pubsub connection
            self.pubsub = self.redis_client.pubsub()
            self.logger.info("PubSub connection created")

            # Subscribe to any existing active channels
            await self._subscribe_to_active_channels()
            self.logger.info("Initial channel subscriptions completed")

            # Listen for messages - keep connection open until service stops
            self.logger.info("Starting message listening loop...")
            last_subscription_check = 0
            subscription_check_interval = 30  # Check every 30 seconds

            # Ensure we have at least one dummy subscription to keep the loop alive
            if not self.active_quote_subscriptions and not self.active_bar_subscriptions:
                self.logger.info(
                    "No active subscriptions, subscribing to dummy channel to keep loop alive")
                await self.pubsub.subscribe('__dummy__')

            async for message in self.pubsub.listen():
                if not self.running:
                    self.logger.info("Service stopped, breaking message loop")
                    break

                try:
                    # Skip dummy messages
                    if message.get('channel') == '__dummy__':
                        continue

                    # Periodic subscription check
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_subscription_check > subscription_check_interval:
                        last_subscription_check = current_time
                        await self._ensure_all_subscriptions_active()

                    # Log all message types for debugging
                    if message['type'] == 'subscribe':
                        self.logger.info(
                            f"Subscribed to channel: {message['channel']}")
                    elif message['type'] == 'unsubscribe':
                        self.logger.info(
                            f"Unsubscribed from channel: {message['channel']}")
                    elif message['type'] == 'message':
                        self.logger.info(
                            f"Received message on channel: {message['channel']}")
                        await self._handle_redis_message(message)
                    else:
                        self.logger.debug(
                            f"Redis message type: {message['type']} on channel: {message.get('channel', 'N/A')}")

                except Exception as e:
                    self.logger.error(f"Error handling Redis message: {e}")

        except asyncio.CancelledError:
            self.logger.info("Subscription loop cancelled")
        except Exception as e:
            self.logger.error(f"Error in subscription loop: {e}")
            self.logger.error(
                f"Exception details: {type(e).__name__}: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
        finally:
            # Only close pubsub if we're stopping the service
            # Don't close it here as it will be closed in the stop() method
            self.logger.info("Subscription loop ended")

    async def _subscribe_to_active_channels(self) -> None:
        """Subscribe to all currently active channels"""
        try:
            channels = []
            for ticker in self.active_quote_subscriptions:
                channels.append(f"quotes:{ticker}")
            for ticker, interval in self.active_bar_subscriptions:
                channels.append(f"bars:{ticker}:{interval}")

            if channels:
                self.logger.info(
                    f"Subscribing to {len(channels)} Redis channels: {channels}")
                await self.pubsub.subscribe(*channels)
                self.logger.info(
                    f"Subscribed to {len(channels)} Redis channels: {channels}")
                # Log active subscriptions for debugging
                self.logger.info(
                    f"Active quote subscriptions: {list(self.active_quote_subscriptions)}")
                self.logger.info(
                    f"Active bar subscriptions: {list(self.active_bar_subscriptions)}")
            else:
                self.logger.info(
                    "No active channels to subscribe to - waiting for subscriptions to be added")

        except Exception as e:
            self.logger.error(f"Error subscribing to active channels: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")

    async def _refresh_when_ready(self) -> None:
        """Refresh subscriptions when the service becomes ready"""
        max_attempts = 10
        attempt = 0

        while attempt < max_attempts and (not self.pubsub or not self.running):
            attempt += 1
            self.logger.info(
                f"Waiting for service to be ready (attempt {attempt}/{max_attempts})")
            await asyncio.sleep(1)

        if self.pubsub and self.running:
            self.logger.info("Service is now ready, refreshing subscriptions")
            await self._subscribe_to_active_channels()
        else:
            self.logger.error(
                "Service failed to become ready after maximum attempts")

    async def refresh_subscriptions(self) -> None:
        """Refresh all active subscriptions by reconnecting to Redis"""
        try:
            self.logger.info("Refreshing Redis subscriptions...")

            # Store current subscriptions before stopping
            current_quote_subs = self.active_quote_subscriptions.copy()
            current_bar_subs = self.active_bar_subscriptions.copy()

            # Stop current service
            await self.stop()

            # Wait a moment
            await asyncio.sleep(0.5)

            # Restart service
            await self.start()

            # Wait for pubsub to be ready
            max_wait = 10  # seconds
            wait_count = 0
            while not self.pubsub and self.running and wait_count < max_wait:
                await asyncio.sleep(0.5)
                wait_count += 1

            if not self.pubsub or not self.running:
                raise RuntimeError(
                    "Failed to establish pubsub connection during refresh")

            # Re-subscribe to all active channels
            for ticker in current_quote_subs:
                await self.pubsub.subscribe(f"quotes:{ticker}")
                self.logger.info(f"Re-subscribed to quotes:{ticker}")

            for ticker, interval in current_bar_subs:
                await self.pubsub.subscribe(f"bars:{ticker}:{interval}")
                self.logger.info(f"Re-subscribed to bars:{ticker}:{interval}")

            self.logger.info("Redis subscriptions refreshed successfully")

        except Exception as e:
            self.logger.error(f"Failed to refresh subscriptions: {e}")
            raise

    async def _handle_redis_message(self, message: Dict[str, Any]) -> None:
        """Handle incoming Redis message and forward to WebSocket clients"""
        try:
            if message['type'] != 'message':
                return

            channel = message['channel']
            data = message['data']

            # Only log at debug level to avoid log flooding
            self.logger.debug(f"Received Redis message on channel: {channel}")

            # Parse the data
            if isinstance(data, bytes):
                data = data.decode('utf-8')
            parsed_data = json.loads(data)

            # Only log parsed data at debug level
            self.logger.debug(f"Parsed message data: {parsed_data}")

            # Determine message type and format for WebSocket
            if channel.startswith('quotes:'):
                await self._handle_quote_message(channel, parsed_data)
            elif channel.startswith('bars:'):
                await self._handle_bar_message(channel, parsed_data)
            else:
                self.logger.warning(f"Unknown channel type: {channel}")

        except Exception as e:
            self.logger.error(f"Error processing Redis message: {e}")
            self.logger.error(f"Message: {message}")

    async def _handle_quote_message(self, channel: str, data: Dict[str, Any]) -> None:
        """Handle quote message from Redis and format for WebSocket"""
        try:
            self.logger.info(f"Handling quote message from {channel}: {data}")
            # Extract ticker from channel (quotes:AAPL -> AAPL)
            ticker = channel.split(':', 1)[1]

            # BarsManager sends quotes with different field names
            # Handle both BarsManager format and standard format
            price = data.get('price', 0)
            change = data.get('change', 0)
            change_percent = data.get('change_percent', 0)
            volume = data.get('volume', 0)

            # BarsManager uses 'time' field for timestamp
            timestamp = data.get('time')
            if timestamp:
                # Convert Unix timestamp to ISO format
                # Handle both seconds and milliseconds
                try:
                    timestamp_int = int(timestamp)
                    # If timestamp is less than 1 billion, assume it's in seconds
                    # If greater, assume it's in milliseconds
                    if timestamp_int < 1_000_000_000:
                        timestamp = datetime.fromtimestamp(
                            timestamp_int).isoformat()
                    else:
                        timestamp = datetime.fromtimestamp(
                            timestamp_int / 1000).isoformat()
                except (ValueError, TypeError):
                    timestamp = datetime.now().isoformat()
            else:
                timestamp = datetime.now().isoformat()

            # Format quote message for WebSocket
            quote_message = {
                'type': 'quote',
                'data': {
                    'symbol': ticker,
                    'price': price,
                    'change': change,
                    'changePercent': change_percent,
                    'volume': volume,
                    'timestamp': timestamp
                },
                'timestamp': datetime.now().isoformat()
            }

            self.logger.info(
                f"Formatted quote message for WebSocket: {quote_message}")

            # Broadcast to WebSocket clients
            self.logger.info(f"Calling broadcast callback for {ticker}")
            await self.broadcast_callback(json.dumps(quote_message))
            self.logger.info(
                f"Successfully forwarded quote for {ticker}: ${price} ({change_percent:+.2f}%)")

        except Exception as e:
            self.logger.error(f"Error handling quote message: {e}")
            self.logger.error(f"Quote data: {data}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")

    async def _handle_bar_message(self, channel: str, data: Dict[str, Any]) -> None:
        """Handle bar message from Redis and format for WebSocket"""
        try:
            # Extract ticker and interval from channel (bars:AAPL:5m -> AAPL, 5m)
            parts = channel.split(':', 2)
            if len(parts) != 3:
                self.logger.error(
                    f"Invalid bar channel format: {channel}, expected format: bars:ticker:interval")
                return
            ticker, interval = parts[1], parts[2]

            # Format bar message for WebSocket
            bar_message = {
                'type': 'bars',
                'data': {
                    'symbol': ticker,
                    'interval': interval,
                    'bars': [{
                        'timestamp': data.get('timestamp', 0),
                        'open': data.get('open', 0),
                        'high': data.get('high', 0),
                        'low': data.get('low', 0),
                        'close': data.get('close', 0),
                        'volume': data.get('volume', 0)
                    }],
                    'is_snapshot': False
                },
                'timestamp': datetime.now().isoformat()
            }

            # Use room-based broadcasting if available, otherwise fall back to global broadcast
            if self.room_broadcast_callback:
                # Route to specific room for this ticker/interval combination
                room_id = f"bars:{ticker}:{interval}"
                await self.room_broadcast_callback(room_id, ticker, bar_message)
                self.logger.debug(
                    f"Routed {interval} bar for {ticker} to room {room_id}")
            else:
                # Fallback to global broadcast
                await self.broadcast_callback(json.dumps(bar_message))
                self.logger.debug(
                    f"Forwarded {interval} bar for {ticker} via global broadcast")

        except Exception as e:
            self.logger.error(f"Error handling bar message: {e}")
            self.logger.error(f"Bar data: {data}")

    def get_active_subscriptions(self) -> Dict[str, Any]:
        """Get current active subscriptions for monitoring"""
        return {
            'quotes': list(self.active_quote_subscriptions),
            'bars': [f"{ticker}:{interval}" for ticker, interval in self.active_bar_subscriptions]
        }

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the service"""
        return {
            'running': self.running,
            'pubsub_ready': self.pubsub is not None,
            'subscription_task_running': self.subscription_task is not None and not self.subscription_task.done(),
            'active_quote_subscriptions': list(self.active_quote_subscriptions),
            'active_bar_subscriptions': [f"{ticker}:{interval}" for ticker, interval in self.active_bar_subscriptions],
            'subscription_task_done': self.subscription_task.done() if self.subscription_task else None,
            'subscription_task_exception': self.subscription_task.exception() if self.subscription_task and self.subscription_task.done() else None
        }

    async def debug_subscription_status(self) -> Dict[str, Any]:
        """Debug method to check subscription status"""
        try:
            status = {
                'service_running': self.running,
                'pubsub_ready': self.pubsub is not None,
                'active_quote_subscriptions': list(self.active_quote_subscriptions),
                'active_bar_subscriptions': [f"{ticker}:{interval}" for ticker, interval in self.active_bar_subscriptions],
                'subscription_task_running': self.subscription_task is not None and not self.subscription_task.done(),
            }

            # Check Redis pubsub status
            if self.pubsub:
                try:
                    # Get current channel subscriptions from Redis
                    channels = await self.redis_client.pubsub_channels()
                    status['redis_subscribed_channels'] = [
                        ch.decode('utf-8') if isinstance(ch, bytes) else ch for ch in channels]

                    # Check if our expected channels are subscribed
                    expected_quote_channels = [
                        f"quotes:{ticker}" for ticker in self.active_quote_subscriptions]
                    expected_bar_channels = [
                        f"bars:{ticker}:{interval}" for ticker, interval in self.active_bar_subscriptions]

                    status['expected_quote_channels'] = expected_quote_channels
                    status['expected_bar_channels'] = expected_bar_channels
                    status['missing_quote_channels'] = [
                        ch for ch in expected_quote_channels if ch not in status['redis_subscribed_channels']]
                    status['missing_bar_channels'] = [
                        ch for ch in expected_bar_channels if ch not in status['redis_subscribed_channels']]

                except Exception as e:
                    status['redis_error'] = str(e)
            else:
                status['redis_subscribed_channels'] = []
                status['expected_quote_channels'] = []
                status['expected_bar_channels'] = []
                status['missing_quote_channels'] = []
                status['missing_bar_channels'] = []

            return status

        except Exception as e:
            return {'error': f'Failed to get debug status: {str(e)}'}

    async def force_resubscribe(self) -> None:
        """Force resubscribe to all active channels"""
        try:
            if not self.pubsub or not self.running:
                self.logger.warning("Cannot resubscribe - service not ready")
                return

            self.logger.info("Force resubscribing to all active channels...")

            # Unsubscribe from all current channels
            if self.pubsub:
                await self.pubsub.unsubscribe()
                self.logger.info("Unsubscribed from all channels")

            # Wait a moment
            await asyncio.sleep(0.1)

            # Resubscribe to active channels
            await self._subscribe_to_active_channels()
            self.logger.info("Force resubscribe completed")

        except Exception as e:
            self.logger.error(f"Error during force resubscribe: {e}")

    async def _ensure_all_subscriptions_active(self) -> None:
        """Ensure all active subscriptions are properly subscribed to Redis channels"""
        if not self.pubsub or not self.running:
            self.logger.warning(
                "Cannot ensure subscriptions - service not ready")
            return

        try:
            # Subscribe to all active quote subscriptions
            for ticker in self.active_quote_subscriptions:
                try:
                    await self.pubsub.subscribe(f"quotes:{ticker}")
                    self.logger.info(
                        f"Ensured Redis subscription to quotes:{ticker}")
                except Exception as e:
                    self.logger.error(
                        f"Failed to ensure subscription to quotes:{ticker}: {e}")

            # Subscribe to all active bar subscriptions
            for ticker, interval in self.active_bar_subscriptions:
                try:
                    await self.pubsub.subscribe(f"bars:{ticker}:{interval}")
                    self.logger.info(
                        f"Ensured Redis subscription to bars:{ticker}:{interval}")
                except Exception as e:
                    self.logger.error(
                        f"Failed to ensure subscription to bars:{ticker}:{interval}: {e}")

        except Exception as e:
            self.logger.error(f"Error ensuring subscriptions: {e}")

    async def force_refresh_subscriptions(self) -> None:
        """Force refresh all subscriptions to ensure they are active"""
        self.logger.info("Force refreshing all subscriptions")

        if not self.pubsub or not self.running:
            self.logger.warning("Cannot force refresh - service not ready")
            return

        try:
            # Unsubscribe from all channels first
            if self.pubsub:
                await self.pubsub.unsubscribe()
                self.logger.info("Unsubscribed from all channels")

            # Wait a moment
            await asyncio.sleep(0.5)

            # Re-subscribe to all active channels
            await self._subscribe_to_active_channels()
            self.logger.info("Force refresh completed")

        except Exception as e:
            self.logger.error(f"Error during force refresh: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
