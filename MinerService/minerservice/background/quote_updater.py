"""Background service for updating real-time quotes"""

import asyncio
import json
from datetime import datetime
from typing import Any

from minerservice.services.quote_service import QuoteService
from minerservice.websocket.connection_manager import \
    WebSocketConnectionManager


class QuoteUpdater:
    """Background service for updating real-time quotes"""

    def __init__(self, connection_manager: WebSocketConnectionManager):
        self.connection_manager = connection_manager
        self.quote_service = QuoteService()
        self.running = False

    async def start(self) -> None:
        """Start the quote updater service"""
        self.running = True
        print("Quote updater service started")

        while self.running:
            try:
                await self._update_quotes()
                await asyncio.sleep(10)  # Update every 10 seconds
            except Exception as e:
                print(f"Error in quote updater: {e}")
                await asyncio.sleep(30)  # Wait longer on error

    async def stop(self) -> None:
        """Stop the quote updater service"""
        self.running = False
        print("Quote updater service stopped")

    async def _update_quotes(self) -> None:
        """Update quotes for all subscribed symbols"""
        try:
            redis_client = await self.connection_manager.get_redis()
            subscribed_symbols = await redis_client.smembers('websocket:subscribed_symbols')

            for symbol in subscribed_symbols:
                symbol_str = symbol.decode(
                    'utf-8') if isinstance(symbol, bytes) else symbol
                await self._update_symbol_quote(symbol_str, redis_client)

        except Exception as e:
            print(f"Error updating quotes: {e}")

    async def _update_symbol_quote(self, symbol: str, redis_client: Any) -> None:
        """Update quote for a specific symbol"""
        try:
            # Get current cached quote for comparison
            quote_key = self.quote_service.create_quote_cache_key(symbol)
            cached_quote = await redis_client.get(quote_key)

            current_price = 0
            if cached_quote:
                current_quote = self.quote_service.deserialize_quote(
                    cached_quote)
                current_price = current_quote.get('price', 0)

            # Fetch new quote data
            new_quote = self.quote_service.fetch_quote_from_yfinance(symbol)
            new_price = new_quote.get('price', 0)

            # Only update if price actually changed (avoid unnecessary broadcasts)
            if self.quote_service.is_price_changed(current_price, new_price):
                # Update cache
                await redis_client.setex(
                    quote_key,
                    self.quote_service.cache_ttl,
                    self.quote_service.serialize_quote(new_quote)
                )

                # Broadcast to all connected clients
                await self.connection_manager.broadcast(json.dumps({
                    'type': 'quote',
                    'data': new_quote,
                    'timestamp': datetime.now().isoformat()
                }))

                print(f"Updated real quote for {symbol}: ${new_price}")
            else:
                # Update cache with current data even if price didn't change
                # This ensures we have fresh volume and other data
                await redis_client.setex(
                    quote_key,
                    self.quote_service.cache_ttl,
                    self.quote_service.serialize_quote(new_quote)
                )

        except Exception as e:
            print(f"Error updating quote for {symbol}: {e}")
