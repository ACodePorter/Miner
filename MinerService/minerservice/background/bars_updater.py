"""Background service for updating real-time bars"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List

from minerservice.services.bars_service import BarsService
from minerservice.websocket.connection_manager import \
    WebSocketConnectionManager


class BarsUpdater:
    """Background service for updating real-time bars"""

    def __init__(self, connection_manager: WebSocketConnectionManager):
        self.connection_manager = connection_manager
        self.bars_service = BarsService()
        self.running = False

    async def start(self) -> None:
        """Start the bars updater service"""
        self.running = True
        print("Bars updater service started")

        while self.running:
            try:
                await self._update_bars()
                await asyncio.sleep(5)  # Check every 5 seconds
            except Exception as e:
                print(f"Error in bars updater: {e}")
                await asyncio.sleep(10)  # Wait longer on error

    async def _update_bars(self) -> None:
        """Update bars for all subscribed symbols"""
        try:
            redis_client = await self.connection_manager.get_redis()
            subscribed_bars = await redis_client.smembers('websocket:subscribed_bars')

            if subscribed_bars:
                print(f"Monitoring {len(subscribed_bars)} bars subscriptions")
            else:
                print("No bars subscriptions to monitor")

            for key in subscribed_bars:
                try:
                    key_str = key.decode(
                        'utf-8') if isinstance(key, bytes) else key
                    sym, interval = key_str.split('|')
                    await self._process_bars_update(sym, interval, redis_client)
                except Exception as e:
                    print(f"Error processing bars update for {key}: {e}")

        except Exception as e:
            print(f"Error updating bars: {e}")

    async def _process_bars_update(self, symbol: str, interval: str, redis_client: Any) -> None:
        """Process bars update for a specific symbol and interval"""
        try:
            print(f"Checking bars for {symbol} {interval}...")

            # Get recent bars for comparison
            hist = self.bars_service.get_recent_bars_for_comparison(
                symbol, interval, 10)
            if hist is None or hist.empty:
                print(f"No bars data for {symbol} {interval}")
                return

            print(f"Got {len(hist)} recent bars for {symbol} {interval}")

            # Get the latest bar
            last_row = hist.iloc[-1]
            last_idx = hist.index[-1]

            # Check if this is the same data as last time we checked
            current_data_hash = self.bars_service.create_bars_data_hash({
                'open': last_row['Open'],
                'high': last_row['High'],
                'low': last_row['Low'],
                'close': last_row['Close'],
                'volume': last_row['Volume']
            })

            last_check_hash_key = self.bars_service.create_last_check_hash_key(
                symbol, interval)
            last_check_hash = await redis_client.get(last_check_hash_key)

            if last_check_hash and last_check_hash == current_data_hash:
                print(
                    f"Data unchanged from last check for {symbol} {interval} - skipping")
                return
            else:
                # Store the new hash for next comparison
                await redis_client.setex(last_check_hash_key, 60, current_data_hash)
                print(
                    f"Data changed from last check for {symbol} {interval} - proceeding")

            # Process the bars update
            bars = await self._get_incremental_bars(symbol, interval, last_row, last_idx, redis_client)

            # Broadcast bars if we have updates
            if bars:
                print(
                    f"Broadcasting {len(bars)} incremental bars for {symbol} {interval}")
                message = self.bars_service.format_bars_message(
                    symbol, interval, bars, is_snapshot=False)
                await self.connection_manager.broadcast(json.dumps(message))
            else:
                print(
                    f"No incremental bars to broadcast for {symbol} {interval}")

        except Exception as e:
            print(f"Error processing bars update for {symbol} {interval}: {e}")

    async def _get_incremental_bars(self, symbol: str, interval: str, last_row: Any, last_idx: Any, redis_client: Any) -> List[Dict[str, Any]]:
        """Get incremental bars data for broadcasting"""
        bars = []
        last_ts_ms = int(last_idx.timestamp() * 1000)
        prev_ts_ms = self.connection_manager.get_last_bars_timestamp(
            symbol, interval)

        # Check if the bar is too old (market closed)
        bar_time = datetime.fromtimestamp(last_idx.timestamp())
        if self.bars_service.is_bar_too_old(bar_time, interval):
            print(f"Bar too old for {symbol} {interval}, skipping")
            return bars

        print(f"Latest bar timestamp: {last_ts_ms}, Previous: {prev_ts_ms}")

        if prev_ts_ms is None:
            # First time - don't send anything, just store timestamp
            self.connection_manager.set_last_bars_timestamp(
                symbol, interval, last_ts_ms)
            print(
                f"Initial timestamp stored for {symbol} {interval}: {last_ts_ms}")

            # Cache current data for future comparison
            await self._cache_bars_data(symbol, interval, last_ts_ms, last_row, redis_client)

        elif last_ts_ms > prev_ts_ms:
            # New bar completed - this is truly incremental
            bars.append({
                'timestamp': last_ts_ms,
                'open': float(last_row['Open']),
                'high': float(last_row['High']),
                'low': float(last_row['Low']),
                'close': float(last_row['Close']),
                'volume': int(last_row['Volume'])
            })
            self.connection_manager.set_last_bars_timestamp(
                symbol, interval, last_ts_ms)
            print(
                f"New incremental bar sent for {symbol} {interval}: {last_ts_ms}")

            # Cache current data for future comparison
            await self._cache_bars_data(symbol, interval, last_ts_ms, last_row, redis_client)

        elif last_ts_ms == prev_ts_ms:
            # Same timestamp - check if data actually changed (for forming bars)
            bars.extend(await self._handle_forming_bar_update(symbol, interval, last_ts_ms, last_row, redis_client))

        return bars

    async def _handle_forming_bar_update(self, symbol: str, interval: str, timestamp: int, last_row: Any, redis_client: Any) -> List[Dict[str, Any]]:
        """Handle forming bar updates (same timestamp, different data)"""
        bars = []

        current_data = {
            'open': float(last_row['Open']),
            'high': float(last_row['High']),
            'low': float(last_row['Low']),
            'close': float(last_row['Close']),
            'volume': int(last_row['Volume'])
        }

        # Get previous data from cache to compare
        prev_data_key = self.bars_service.create_bars_cache_key(
            symbol, interval, timestamp)
        prev_data_str = await redis_client.get(prev_data_key)

        if prev_data_str:
            prev_data = self.bars_service.deserialize_bars_data(prev_data_str)

            # Check if data actually changed
            data_changed = self._has_meaningful_change(current_data, prev_data)

            if data_changed:
                # Check if we already sent this exact data recently
                data_hash = self.bars_service.create_bars_data_hash(
                    current_data)
                last_sent_hash_key = self.bars_service.create_bars_hash_cache_key(
                    symbol, interval, timestamp)
                last_sent_hash = await redis_client.get(last_sent_hash_key)

                if last_sent_hash and last_sent_hash == data_hash:
                    print(
                        f"Data already sent for {symbol} {interval} - skipping duplicate")
                else:
                    # Data changed and not duplicate, send incremental update
                    bars.append({
                        'timestamp': timestamp,
                        **current_data
                    })
                    print(
                        f"Forming bar update sent for {symbol} {interval} - data changed")

                    # Store the hash to prevent duplicates
                    await redis_client.setex(last_sent_hash_key, 300, data_hash)
            else:
                print(
                    f"No meaningful change for {symbol} {interval} - skipping update")
        else:
            # No previous data to compare, cache current data
            await self._cache_bars_data(symbol, interval, timestamp, last_row, redis_client)
            print(
                f"Cached data for {symbol} {interval} - no previous data to compare")

        return bars

    def _has_meaningful_change(self, current: Dict[str, Any], previous: Dict[str, Any]) -> bool:
        """Check if there's meaningful change between current and previous data"""
        threshold = 0.001
        return (abs(current['high'] - previous['high']) > threshold or
                abs(current['low'] - previous['low']) > threshold or
                abs(current['close'] - previous['close']) > threshold or
                abs(current['volume'] - previous['volume']) > 0)

    async def _cache_bars_data(self, symbol: str, interval: str, timestamp: int, row: Any, redis_client: Any) -> None:
        """Cache bars data for future comparison"""
        current_data = {
            'open': float(row['Open']),
            'high': float(row['High']),
            'low': float(row['Low']),
            'close': float(row['Close']),
            'volume': int(row['Volume'])
        }

        prev_data_key = self.bars_service.create_bars_cache_key(
            symbol, interval, timestamp)
        await redis_client.setex(
            prev_data_key,
            self.bars_service.cache_ttl,
            self.bars_service.serialize_bars_data(current_data)
        )
