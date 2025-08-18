"""WebSocket message handler for processing client messages"""

import json
from datetime import datetime
from typing import Any, Dict

from fastapi import WebSocket
from minerservice.services.bars_service import BarsService
from minerservice.websocket.connection_manager import \
    WebSocketConnectionManager


class WebSocketMessageHandler:
    """Handles WebSocket message processing and routing"""

    def __init__(self, connection_manager: WebSocketConnectionManager):
        self.connection_manager = connection_manager
        self.bars_service = BarsService()

    async def handle_message(self, websocket: WebSocket, client_id: str, message_data: Dict[str, Any]) -> None:
        """Route and handle incoming WebSocket messages"""
        message_type = message_data.get('type')

        handlers = {
            'subscribe': self._handle_subscribe,
            'unsubscribe': self._handle_unsubscribe,
            'get_quote': self._handle_get_quote,
            'subscribe_bars': self._handle_subscribe_bars,
            'unsubscribe_bars': self._handle_unsubscribe_bars,
            'ping': self._handle_ping,
            'broadcast': self._handle_broadcast
        }

        handler = handlers.get(message_type)
        if handler:
            await handler(websocket, client_id, message_data)
        else:
            await self._send_error(websocket, f'Unknown message type: {message_type}')

    async def _handle_subscribe(self, websocket: WebSocket, client_id: str, message_data: Dict[str, Any]) -> None:
        """Handle symbol subscription"""
        symbol = message_data.get('symbol')
        if not symbol:
            await self._send_error(websocket, 'Symbol is required for subscription')
            return

        await self.connection_manager.subscribe_symbol(symbol)

        # Send subscription confirmation
        await websocket.send_text(json.dumps({
            'type': 'subscribed',
            'symbol': symbol,
            'timestamp': datetime.now().isoformat()
        }))

        # Send initial quote data
        await self._send_initial_quote(websocket, symbol)

    async def _handle_unsubscribe(self, websocket: WebSocket, client_id: str, message_data: Dict[str, Any]) -> None:
        """Handle symbol unsubscription"""
        symbol = message_data.get('symbol')
        if symbol:
            await websocket.send_text(json.dumps({
                'type': 'unsubscribed',
                'symbol': symbol,
                'timestamp': datetime.now().isoformat()
            }))

    async def _handle_get_quote(self, websocket: WebSocket, client_id: str, message_data: Dict[str, Any]) -> None:
        """Handle quote request"""
        symbol = message_data.get('symbol')
        if not symbol:
            await self._send_error(websocket, 'Symbol is required for quote request')
            return

        quote_data = await self._get_quote_data(symbol)
        await websocket.send_text(json.dumps({
            'type': 'quote',
            'data': quote_data,
            'timestamp': datetime.now().isoformat()
        }))

    async def _handle_subscribe_bars(self, websocket: WebSocket, client_id: str, message_data: Dict[str, Any]) -> None:
        """Handle bars subscription"""
        symbol = message_data.get('symbol')
        interval = message_data.get('interval')

        if not symbol or not interval:
            await self._send_error(websocket, 'Symbol and interval are required for bars subscription')
            return

        await self.connection_manager.subscribe_bars(symbol, interval)

        # Send subscription confirmation
        await websocket.send_text(json.dumps({
            'type': 'subscribed_bars',
            'symbol': symbol,
            'interval': interval,
            'timestamp': datetime.now().isoformat()
        }))

        # Send initial bars snapshot
        await self._send_initial_bars(websocket, symbol, interval)

    async def _handle_unsubscribe_bars(self, websocket: WebSocket, client_id: str, message_data: Dict[str, Any]) -> None:
        """Handle bars unsubscription"""
        symbol = message_data.get('symbol')
        interval = message_data.get('interval')

        if symbol and interval:
            await self.connection_manager.unsubscribe_bars(symbol, interval)
            await websocket.send_text(json.dumps({
                'type': 'unsubscribed_bars',
                'symbol': symbol,
                'interval': interval,
                'timestamp': datetime.now().isoformat()
            }))

    async def _handle_ping(self, websocket: WebSocket, client_id: str, message_data: Dict[str, Any]) -> None:
        """Handle ping/pong for connection health"""
        await websocket.send_text(json.dumps({
            'type': 'pong',
            'timestamp': datetime.now().isoformat()
        }))

    async def _handle_broadcast(self, websocket: WebSocket, client_id: str, message_data: Dict[str, Any]) -> None:
        """Handle client broadcast messages"""
        broadcast_message = message_data.get('message', '')
        if broadcast_message:
            await self.connection_manager.broadcast_to_all_processes(broadcast_message)
            await websocket.send_text(json.dumps({
                'type': 'broadcast_sent',
                'message': broadcast_message,
                'timestamp': datetime.now().isoformat()
            }))

    async def _send_initial_quote(self, websocket: WebSocket, symbol: str) -> None:
        """Send initial quote data for a subscribed symbol"""
        try:
            # Try to get initial quote from BarsManager integration first
            if (self.connection_manager.bars_manager_integration and
                    self.connection_manager.bars_manager_integration.is_subscribed_to_quotes(symbol)):
                quote_data = await self.connection_manager.bars_manager_integration.get_initial_quote(symbol)
                if quote_data:
                    await websocket.send_text(json.dumps({
                        'type': 'quote',
                        'data': quote_data,
                        'timestamp': datetime.now().isoformat()
                    }))
                    return

            # Fallback to existing quote service
            quote_data = await self._get_quote_data(symbol)
            await websocket.send_text(json.dumps({
                'type': 'quote',
                'data': quote_data,
                'timestamp': datetime.now().isoformat()
            }))
        except Exception as e:
            print(f"Error sending initial quote for {symbol}: {e}")

    async def _send_initial_bars(self, websocket: WebSocket, symbol: str, interval: str) -> None:
        """Send initial bars snapshot for a subscribed symbol"""
        try:
            # Try to get initial bars from BarsManager integration first
            if (self.connection_manager.bars_manager_integration and
                    self.connection_manager.bars_manager_integration.is_subscribed_to_bars(symbol, interval)):
                bars = await self.connection_manager.bars_manager_integration.get_initial_bars_snapshot(symbol, interval)
                if bars:
                    print(
                        f"Sending initial bars snapshot for {symbol} {interval}: {len(bars)} bars")

                    # Send initial snapshot
                    await websocket.send_text(json.dumps({
                        'type': 'bars',
                        'data': {
                            'symbol': symbol,
                            'interval': interval,
                            'bars': bars,
                            'is_snapshot': True
                        }
                    }))

                    # Store the last timestamp for this stream using the connection manager
                    if bars:
                        last_ts = bars[-1]['timestamp']
                        self.connection_manager.set_last_bars_timestamp(
                            symbol, interval, last_ts)
                        print(
                            f"Stored last timestamp for {symbol} {interval}: {last_ts}")
                    return

            # Fallback to existing bars service
            bars = self.bars_service.get_initial_bars_snapshot(
                symbol, interval)

            if bars:
                print(
                    f"Sending initial bars snapshot for {symbol} {interval}: {len(bars)} bars")

                # Send initial snapshot
                await websocket.send_text(json.dumps({
                    'type': 'bars',
                    'data': {
                        'symbol': symbol,
                        'interval': interval,
                        'bars': bars,
                        'is_snapshot': True
                    }
                }))

                # Store the last timestamp for this stream using the connection manager
                if bars:
                    last_ts = bars[-1]['timestamp']
                    self.connection_manager.set_last_bars_timestamp(
                        symbol, interval, last_ts)
                    print(
                        f"Stored last timestamp for {symbol} {interval}: {last_ts}")

        except Exception as e:
            print(f"Error sending initial bars for {symbol} {interval}: {e}")

    async def _get_quote_data(self, symbol: str) -> Dict[str, Any]:
        """Get quote data from BarsManager integration or return fallback"""
        try:
            # Try to get quote from BarsManager integration first
            if self.connection_manager.bars_manager_integration:
                quote_data = await self.connection_manager.bars_manager_integration.get_initial_quote(symbol)
                if quote_data:
                    return quote_data

            # Fallback: return placeholder data indicating no quote available
            return {
                'symbol': symbol,
                'price': 0,
                'change': 0,
                'changePercent': 0,
                'volume': 0,
                'timestamp': datetime.now().isoformat(),
                'status': 'no_data_available'
            }

        except Exception as e:
            print(f"Error getting quote for {symbol}: {e}")
            # Return fallback data
            return {
                'symbol': symbol,
                'price': 0,
                'change': 0,
                'changePercent': 0,
                'volume': 0,
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }

    async def _send_error(self, websocket: WebSocket, message: str) -> None:
        """Send error message to client"""
        await websocket.send_text(json.dumps({
            'type': 'error',
            'message': message
        }))
