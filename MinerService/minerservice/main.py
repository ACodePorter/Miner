import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime

# yfinance import removed - using BarsManager integration only
from detonator import get_logger
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .api.v1 import api_v1_router
from .ws.connection_manager import WebSocketConnectionManager, manager

_logger = get_logger('MinerService', logging.DEBUG)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI startup/shutdown events"""
    global manager

    # Startup
    manager = WebSocketConnectionManager()
    await manager.startup()

    # Start background tasks
    quote_updates_task = asyncio.create_task(update_real_quotes())
    bars_updates_task = asyncio.create_task(monitor_bars_updates())

    yield

    # Shutdown
    if quote_updates_task:
        quote_updates_task.cancel()
        try:
            await quote_updates_task
        except asyncio.CancelledError:
            pass

    if bars_updates_task:
        bars_updates_task.cancel()
        try:
            await bars_updates_task
        except asyncio.CancelledError:
            pass

    if manager:
        await manager.shutdown()

app = FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 router with all organized endpoints
app.include_router(api_v1_router)

# WebSocket connection manager with BarsManager integration
# Uses WebSocketConnectionManager from websocket/connection_manager.py


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time communication with BarsManager integration"""
    if not manager:
        await websocket.close(code=1011, reason="Service unavailable")
        return

    try:
        await manager.connect(websocket, client_id)
        print(f"WebSocket client connected: {client_id}")

        # Send welcome message
        await websocket.send_text(json.dumps({
            'type': 'connected',
            'client_id': client_id,
            'message': 'Connected to WebSocket service with BarsManager integration',
            'timestamp': datetime.now().isoformat()
        }))

        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                _logger.info(f"Received message: {message}")

                if message.get('type') == 'subscribe':
                    symbol = message.get('symbol')
                    if not symbol:
                        await websocket.send_text(json.dumps({
                            'type': 'error',
                            'message': 'Symbol is required for subscription',
                            'timestamp': datetime.now().isoformat()
                        }))
                        continue

                    # Validate symbol format (basic validation)
                    if not isinstance(symbol, str) or len(symbol.strip()) == 0:
                        await websocket.send_text(json.dumps({
                            'type': 'error',
                            'message': 'Invalid symbol format',
                            'timestamp': datetime.now().isoformat()
                        }))
                        continue

                    symbol = symbol.strip().upper()

                    try:
                        # Subscribe via room manager for automatic data broadcasting
                        if manager.room_manager:
                            room_id = await manager.room_manager.subscribe_to_quotes(symbol)

                            # Join the client to the quote room
                            await manager.room_manager.join_room(client_id, room_id)

                            await websocket.send_text(json.dumps({
                                'type': 'subscribed',
                                'symbol': symbol,
                                'room_id': room_id,
                                'message': f'Subscribed to {symbol} quotes and joined room {room_id}',
                                'timestamp': datetime.now().isoformat()
                            }))
                            print(
                                f"Client {client_id} subscribed to {symbol} quotes and joined room {room_id}")
                        else:
                            # Fallback to old method
                            await manager.subscribe_symbol(symbol)
                            await websocket.send_text(json.dumps({
                                'type': 'subscribed',
                                'symbol': symbol,
                                'timestamp': datetime.now().isoformat()
                            }))
                            print(
                                f"Client {client_id} subscribed to {symbol} (fallback method)")

                        # Send initial quote data
                        try:
                            if manager.bars_manager_integration:
                                quote_data = await manager.bars_manager_integration.get_initial_quote(symbol)
                                if quote_data:
                                    if quote_data.get('status') == 'subscribed_waiting_for_data':
                                        await websocket.send_text(json.dumps({
                                            'type': 'subscribed',
                                            'symbol': symbol,
                                            'message': f'{symbol} subscribed to live quotes, waiting for data...',
                                            'timestamp': datetime.now().isoformat()
                                        }))
                                    else:
                                        await websocket.send_text(json.dumps({
                                            'type': 'quote',
                                            'data': quote_data,
                                            'timestamp': datetime.now().isoformat()
                                        }))
                                else:
                                    await websocket.send_text(json.dumps({
                                        'type': 'error',
                                        'message': f'No quote data available for {symbol}',
                                        'timestamp': datetime.now().isoformat()
                                    }))
                        except Exception as e:
                            print(
                                f"Error sending initial quote for {symbol}: {e}")

                    except Exception as e:
                        print(f"Error subscribing to symbol {symbol}: {e}")
                        await websocket.send_text(json.dumps({
                            'type': 'error',
                            'message': f'Failed to subscribe to {symbol}: {str(e)}',
                            'timestamp': datetime.now().isoformat()
                        }))

                elif message.get('type') == 'subscribe_bars':
                    symbol = message.get('symbol')
                    interval = message.get('interval', '5m')

                    if not symbol or not interval:
                        await websocket.send_text(json.dumps({
                            'type': 'error',
                            'message': 'Both symbol and interval are required for bars subscription',
                            'timestamp': datetime.now().isoformat()
                        }))
                        continue

                    # Validate symbol and interval
                    if not isinstance(symbol, str) or len(symbol.strip()) == 0:
                        await websocket.send_text(json.dumps({
                            'type': 'error',
                            'message': 'Invalid symbol format',
                            'timestamp': datetime.now().isoformat()
                        }))
                        continue

                    symbol = symbol.strip().upper()

                    # Validate interval
                    allowed_intervals = {'1m', '5m', '15m',
                                         '30m', '65m', '1d', '1wk', '1mo', '3mo'}
                    if interval not in allowed_intervals:
                        await websocket.send_text(json.dumps({
                            'type': 'error',
                            'message': f'Invalid interval: {interval}. Allowed: {", ".join(sorted(allowed_intervals))}',
                            'timestamp': datetime.now().isoformat()
                        }))
                        continue

                    try:
                        # Subscribe via room manager for automatic data broadcasting
                        if manager.room_manager:
                            room_id = await manager.room_manager.subscribe_to_bars(symbol, interval)

                            # Join the client to the bar room
                            await manager.room_manager.join_room(client_id, room_id)

                            await websocket.send_text(json.dumps({
                                'type': 'bars_subscribed',
                                'symbol': symbol,
                                'interval': interval,
                                'room_id': room_id,
                                'message': f'Subscribed to {symbol} {interval} bars and joined room {room_id}',
                                'timestamp': datetime.now().isoformat()
                            }))
                            print(
                                f"Client {client_id} subscribed to {symbol} {interval} bars and joined room {room_id}")
                        else:
                            # Fallback to old method
                            await manager.subscribe_bars(symbol, interval)
                            await websocket.send_text(json.dumps({
                                'type': 'bars_subscribed',
                                'symbol': symbol,
                                'interval': interval,
                                'timestamp': datetime.now().isoformat()
                            }))
                            print(
                                f"Client {client_id} subscribed to {symbol} {interval} bars (fallback method)")

                        # Send initial bars data
                        try:
                            if manager.bars_manager_integration:
                                bars_data = await manager.bars_manager_integration.get_initial_bars_snapshot(symbol, interval)
                                if bars_data:
                                    await websocket.send_text(json.dumps({
                                        'type': 'bars',
                                        'data': {
                                            'symbol': symbol,
                                            'interval': interval,
                                            'bars': bars_data,
                                            'is_snapshot': True
                                        },
                                        'timestamp': datetime.now().isoformat()
                                    }))
                                else:
                                    await websocket.send_text(json.dumps({
                                        'type': 'error',
                                        'message': f'No bars data available for {symbol} {interval}',
                                        'timestamp': datetime.now().isoformat()
                                    }))
                        except Exception as e:
                            print(
                                f"Error sending initial bars for {symbol} {interval}: {e}")

                    except Exception as e:
                        print(
                            f"Error subscribing to bars for {symbol} {interval}: {e}")
                        await websocket.send_text(json.dumps({
                            'type': 'error',
                            'message': f'Failed to subscribe to bars for {symbol} {interval}: {str(e)}',
                            'timestamp': datetime.now().isoformat()
                        }))

                elif message.get('type') == 'unsubscribe':
                    symbol = message.get('symbol')
                    if not symbol:
                        await websocket.send_text(json.dumps({
                            'type': 'error',
                            'message': 'Symbol is required for unsubscription',
                            'timestamp': datetime.now().isoformat()
                        }))
                        continue

                    symbol = symbol.strip().upper()

                    try:
                        await manager.unsubscribe_symbol(symbol)
                        await websocket.send_text(json.dumps({
                            'type': 'unsubscribed',
                            'symbol': symbol,
                            'timestamp': datetime.now().isoformat()
                        }))
                        print(f"Unsubscribed {client_id} from {symbol}")
                    except Exception as e:
                        print(f"Error unsubscribing from symbol {symbol}: {e}")
                        await websocket.send_text(json.dumps({
                            'type': 'error',
                            'message': f'Failed to unsubscribe from {symbol}: {str(e)}',
                            'timestamp': datetime.now().isoformat()
                        }))

                elif message.get('type') == 'unsubscribe_bars':
                    symbol = message.get('symbol')
                    interval = message.get('interval', '5m')

                    if not symbol or not interval:
                        await websocket.send_text(json.dumps({
                            'type': 'error',
                            'message': 'Both symbol and interval are required for bars unsubscription',
                            'timestamp': datetime.now().isoformat()
                        }))
                        continue

                    symbol = symbol.strip().upper()

                    try:
                        await manager.unsubscribe_bars(symbol, interval)
                        await websocket.send_text(json.dumps({
                            'type': 'bars_unsubscribed',
                            'symbol': symbol,
                            'interval': interval,
                            'timestamp': datetime.now().isoformat()
                        }))
                        print(
                            f"Unsubscribed {client_id} from {symbol} {interval} bars")
                    except Exception as e:
                        print(
                            f"Error unsubscribing from bars for {symbol} {interval}: {e}")
                        await websocket.send_text(json.dumps({
                            'type': 'error',
                            'message': f'Failed to unsubscribe from bars for {symbol} {interval}: {str(e)}',
                            'timestamp': datetime.now().isoformat()
                        }))

                elif message.get('type') == 'ping':
                    await websocket.send_text(json.dumps({
                        'type': 'pong',
                        'timestamp': datetime.now().isoformat()
                    }))

                elif message.get('type') == 'join_room':
                    room_id = message.get('room_id')
                    if not room_id:
                        await websocket.send_text(json.dumps({
                            'type': 'error',
                            'message': 'Room ID is required for joining',
                            'timestamp': datetime.now().isoformat()
                        }))
                        continue

                    try:
                        success = await manager.join_room(client_id, room_id)
                        if success:
                            await websocket.send_text(json.dumps({
                                'type': 'room_joined',
                                'room_id': room_id,
                                'timestamp': datetime.now().isoformat()
                            }))
                            print(f"Client {client_id} joined room {room_id}")
                        else:
                            await websocket.send_text(json.dumps({
                                'type': 'error',
                                'message': f'Failed to join room {room_id}',
                                'timestamp': datetime.now().isoformat()
                            }))
                    except Exception as e:
                        print(f"Error joining room {room_id}: {e}")
                        await websocket.send_text(json.dumps({
                            'type': 'error',
                            'message': f'Failed to join room {room_id}: {str(e)}',
                            'timestamp': datetime.now().isoformat()
                        }))

                elif message.get('type') == 'leave_room':
                    room_id = message.get('room_id')
                    if not room_id:
                        await websocket.send_text(json.dumps({
                            'type': 'error',
                            'message': 'Room ID is required for leaving',
                            'timestamp': datetime.now().isoformat()
                        }))
                        continue

                    try:
                        success = await manager.leave_room(client_id, room_id)
                        if success:
                            await websocket.send_text(json.dumps({
                                'type': 'room_left',
                                'room_id': room_id,
                                'timestamp': datetime.now().isoformat()
                            }))
                            print(f"Client {client_id} left room {room_id}")
                        else:
                            await websocket.send_text(json.dumps({
                                'type': 'error',
                                'message': f'Failed to leave room {room_id}',
                                'timestamp': datetime.now().isoformat()
                            }))
                    except Exception as e:
                        print(f"Error leaving room {room_id}: {e}")
                        await websocket.send_text(json.dumps({
                            'type': 'error',
                            'message': f'Failed to leave room {room_id}: {str(e)}',
                            'timestamp': datetime.now().isoformat()
                        }))

                elif message.get('type') == 'room_broadcast':
                    room_id = message.get('room_id')
                    room_message = message.get('message')
                    if not room_id or not room_message:
                        await websocket.send_text(json.dumps({
                            'type': 'error',
                            'message': 'Room ID and message are required for room broadcast',
                            'timestamp': datetime.now().isoformat()
                        }))
                        continue

                    try:
                        client_count = await manager.broadcast_to_room(room_id, room_message, exclude_client=client_id)
                        await websocket.send_text(json.dumps({
                            'type': 'room_broadcast_sent',
                            'room_id': room_id,
                            'client_count': client_count,
                            'timestamp': datetime.now().isoformat()
                        }))
                        print(
                            f"Room broadcast sent to {client_count} clients in room {room_id}")
                    except Exception as e:
                        print(f"Error broadcasting to room {room_id}: {e}")
                        await websocket.send_text(json.dumps({
                            'type': 'error',
                            'message': f'Failed to broadcast to room {room_id}: {str(e)}',
                            'timestamp': datetime.now().isoformat()
                        }))

                elif message.get('type') == 'get_rooms':
                    try:
                        rooms = await manager.get_client_rooms(client_id)
                        await websocket.send_text(json.dumps({
                            'type': 'client_rooms',
                            'rooms': list(rooms),
                            'timestamp': datetime.now().isoformat()
                        }))
                    except Exception as e:
                        print(
                            f"Error getting rooms for client {client_id}: {e}")
                        await websocket.send_text(json.dumps({
                            'type': 'error',
                            'message': f'Failed to get rooms: {str(e)}',
                            'timestamp': datetime.now().isoformat()
                        }))

                else:
                    # Unknown message type
                    await websocket.send_text(json.dumps({
                        'type': 'error',
                        'message': f'Unknown message type: {message.get("type")}',
                        'timestamp': datetime.now().isoformat()
                    }))

            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    'type': 'error',
                    'message': 'Invalid JSON format',
                    'timestamp': datetime.now().isoformat()
                }))
            except Exception as e:
                print(f"Error processing message from {client_id}: {e}")
                await websocket.send_text(json.dumps({
                    'type': 'error',
                    'message': f'Internal server error: {str(e)}',
                    'timestamp': datetime.now().isoformat()
                }))

    except WebSocketDisconnect:
        print(f"WebSocket client disconnected: {client_id}")
    except Exception as e:
        print(f"WebSocket error for {client_id}: {e}")
        # Try to send error message before closing
        try:
            await websocket.send_text(json.dumps({
                'type': 'error',
                'message': f'Connection error: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }))
        except:
            pass  # Ignore errors when sending error message
    finally:
        print(f"🔄 Starting cleanup for disconnected client: {client_id}")
        if manager:
            try:
                # Comprehensive cleanup through the manager
                await manager.disconnect(websocket, client_id)
                print(f"✅ Cleanup completed for client: {client_id}")
            except Exception as e:
                print(
                    f"❌ Error during disconnect cleanup for {client_id}: {e}")
                # Try to force cleanup even if manager fails
                try:
                    if websocket:
                        await websocket.close()
                except:
                    pass
        else:
            print(
                f"⚠️  Manager not available for cleanup of client: {client_id}")
            try:
                if websocket:
                    await websocket.close()
            except:
                pass


async def monitor_bars_updates():
    """Monitor and broadcast real-time bars updates for subscribed symbols"""
    print("Starting bars monitoring service...")
    while True:
        try:
            if manager:
                # Get active subscriptions from BarsManager integration
                if manager.bars_manager_integration:
                    active_subscriptions = manager.bars_manager_integration.get_active_subscriptions()
                    print(f"Active subscriptions: {active_subscriptions}")
                else:
                    print("BarsManager integration not available")

                # Get Redis subscription status
                redis_client = await manager.get_redis()
                subscribed_bars = await redis_client.smembers('websocket:subscribed_bars')

                if subscribed_bars:
                    print(
                        f"WebSocket bars subscriptions: {[key.decode('utf-8') if isinstance(key, bytes) else key for key in subscribed_bars]}")
                else:
                    print("No bars subscriptions to monitor")

                # The actual data monitoring is now handled by BarsManager and Redis subscription service
                # This function just provides status monitoring

            # Wait before next status check
            await asyncio.sleep(30)  # Check status every 30 seconds

        except Exception as e:
            print(f"Error in bars monitoring: {e}")
            await asyncio.sleep(10)  # Wait longer on error


# Background task to simulate real-time quote updates (keeping this for now)
async def update_real_quotes():
    """Fetch and broadcast real-time quote updates for subscribed symbols"""
    while True:
        try:
            if manager:
                # Get active quote subscriptions from BarsManager integration
                if manager.bars_manager_integration:
                    active_quotes = manager.bars_manager_integration.get_active_subscriptions()[
                        'quotes']
                    print(
                        f"Active quote subscriptions via BarsManager: {active_quotes}")
                else:
                    print("BarsManager integration not available for quotes")

                # Get detailed subscription status for monitoring
                subscription_status = await manager.get_subscription_status()
                print(f"Subscription Status: {subscription_status}")

                # Check for subscription mismatches
                if subscription_status.get('memory_quotes') != subscription_status.get('redis_quotes'):
                    print(
                        f"⚠️  Quote subscription mismatch: Memory={subscription_status.get('memory_quotes')}, Redis={subscription_status.get('redis_quotes')}")

                if subscription_status.get('memory_bars') != subscription_status.get('redis_bars'):
                    print(
                        f"⚠️  Bars subscription mismatch: Memory={subscription_status.get('memory_bars')}, Redis={subscription_status.get('redis_bars')}")

                # Show active subscriptions
                if subscription_status.get('memory_quote_symbols'):
                    print(
                        f"Active quote subscriptions: {subscription_status.get('memory_quote_symbols')}")
                else:
                    print("No active quote subscriptions")

                # The actual quote updates are now handled by BarsManager and Redis subscription service
                # This function just provides status monitoring

            # Wait before next status check
            await asyncio.sleep(30)  # Check status every 30 seconds

        except Exception as e:
            print(f"Error in real quote updates: {e}")
            await asyncio.sleep(30)  # Wait longer on error


# Remove all old API endpoints - now handled by routers
# @app.get('/api/realtime/quote/{symbol}')
# @app.get('/api/bars/{symbol}/{interval}')
# @app.get('/api/mbs/{market_index}.json')
# @app.get('/api/market_pe/{index}.json')
# @app.get('/api/wedge_pop/latest.json')
# @app.get('/api/wedge_pop/wedges.json')
# @app.get('/api/wedge_pop/stats.json')
# @app.get('/api/ohlcvw/{ticker}.json')
# @app.get('/api/watchlist')
# @app.post('/api/watchlist')
# @app.delete('/api/watchlist/{ticker}')

# Keep only the WebSocket endpoint and background functions
