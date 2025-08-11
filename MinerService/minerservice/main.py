import asyncio
import json
import os
import random
import signal
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

import pytz
import redis.asyncio as redis
import yfinance as yf
from browserscraper.tasks import update_market_pe_task
from celery import chain
from dataminer import BarsManager, MarketDataShovel, WedgePop
from dataminer.models import MarketPe
from detonator import make_db_connection, mongo_2_df
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from marketbreadth import MarketBreadth
from marketbreadth.tasks import update_spx_market_breadth_task

from .tasks import (run_hk_daily_updates_task, run_us_daily_updates_task,
                    update_indicators_for_tickers_task,
                    update_iw_daily_ma_task,
                    update_iwd_tickers_daily_info_task,
                    update_iwd_tickers_info_task, update_iwd_tickers_task,
                    update_iwf_tickers_daily_info_task,
                    update_iwf_tickers_info_task, update_iwf_tickers_task,
                    update_iwm_tickers_daily_info_task,
                    update_iwm_tickers_info_task, update_iwm_tickers_task,
                    update_spx_daily_ma_task,
                    update_spx_tickers_daily_info_task,
                    update_spx_tickers_info_task, update_spx_tickers_task,
                    update_tickers_daily_info_task,
                    update_us_trade_calendar_task,
                    update_wedge_pop_for_index_task)

# Global manager instance
manager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI startup/shutdown events"""
    global manager

    # Startup
    manager = RedisConnectionManager()
    await manager.startup()

    # Start background quote updates simulation
    quote_updates_task = asyncio.create_task(simulate_quote_updates())

    yield

    # Shutdown
    if quote_updates_task:
        quote_updates_task.cancel()
        try:
            await quote_updates_task
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

# WebSocket connection manager with Redis support


class RedisConnectionManager:
    def __init__(self):
        self.redis_client = None
        self.process_id = str(uuid.uuid4())
        self.local_connections: Dict[str, WebSocket] = {}
        self.subscribed_symbols: Set[str] = set()
        self.broadcast_task = None
        self.heartbeat_task = None
        self.running = False

    async def get_redis(self):
        """Get Redis client with connection pooling for multi-process support"""
        if self.redis_client is None:
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
        else:
            try:
                await self.redis_client.ping()
            except Exception:
                try:
                    await self.redis_client.close()
                except Exception:
                    pass
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
                print(f"Redis reconnected for process {self.process_id}")
        return self.redis_client

    async def connect(self, websocket: WebSocket, client_id: str):
        """Connect a new WebSocket client"""
        try:
            await websocket.accept()
            self.local_connections[client_id] = websocket

            # Store connection info in Redis
            redis_client = await self.get_redis()
            connection_info = {
                'client_id': client_id,
                'process_id': self.process_id,
                'connected_at': datetime.now().isoformat(),
                'last_heartbeat': datetime.now().isoformat()
            }

            # Use pipeline for atomic operations
            async with redis_client.pipeline() as pipe:
                await pipe.hset(f"websocket:connections:{client_id}", mapping=connection_info)
                # 1 hour TTL
                await pipe.expire(f"websocket:connections:{client_id}", 3600)
                await pipe.sadd(f"websocket:processes:{self.process_id}:clients", client_id)
                await pipe.expire(f"websocket:processes:{self.process_id}:clients", 3600)
                await pipe.execute()

            print(f"Client {client_id} connected to process {self.process_id}")

        except Exception as e:
            print(f"Error connecting client {client_id}: {e}")
            raise

    async def disconnect(self, websocket: WebSocket, client_id: str):
        """Disconnect a WebSocket client"""
        try:
            if client_id in self.local_connections:
                del self.local_connections[client_id]

            # Remove from Redis
            redis_client = await self.get_redis()
            async with redis_client.pipeline() as pipe:
                await pipe.delete(f"websocket:connections:{client_id}")
                await pipe.srem(f"websocket:processes:{self.process_id}:clients", client_id)
                await pipe.execute()

            print(
                f"Client {client_id} disconnected from process {self.process_id}")

        except Exception as e:
            print(f"Error disconnecting client {client_id}: {e}")

    async def send_personal_message(self, message: str, client_id: str):
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

    async def broadcast_to_all_processes(self, message: str):
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

    async def broadcast(self, message: str):
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

    async def subscribe_symbol(self, symbol: str):
        """Subscribe to a symbol for real-time quotes"""
        if symbol not in self.subscribed_symbols:
            self.subscribed_symbols.add(symbol)

            try:
                # Store subscription in Redis
                redis_client = await self.get_redis()
                await redis_client.sadd('websocket:subscribed_symbols', symbol)
                print(f"Subscribed to symbol: {symbol}")
            except Exception as e:
                print(f"Error subscribing to symbol {symbol}: {e}")

    async def get_all_connections(self):
        """Get all active connections across all processes"""
        try:
            redis_client = await self.get_redis()
            connections = await redis_client.keys('websocket:connections:*')
            return connections
        except Exception as e:
            print(f"Error getting connections: {e}")
            return []

    async def start_broadcast_listener(self):
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

    async def start_heartbeat(self):
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

    async def cleanup_stale_connections(self):
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

    async def startup(self):
        """Initialize the connection manager"""
        self.running = True
        await self.start_broadcast_listener()
        await self.start_heartbeat()
        print(f"RedisConnectionManager started for process {self.process_id}")

    async def shutdown(self):
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

        print(f"RedisConnectionManager shutdown for process {self.process_id}")


@app.get('/')
async def root():
    return {'Hello': 'World'}


@app.get('/api/websocket/status')
async def get_websocket_status():
    """Get WebSocket service status and connection information"""
    if not manager:
        return {'status': 'unavailable', 'message': 'WebSocket service not initialized'}

    try:
        redis_client = await manager.get_redis()

        # Get connection counts
        local_connections = len(manager.local_connections)
        total_connections = len(await manager.get_all_connections())

        # Get process info
        process_info = {
            'process_id': manager.process_id,
            'local_connections': local_connections,
            'total_connections': total_connections,
            'subscribed_symbols': list(manager.subscribed_symbols),
            'running': manager.running
        }

        # Get Redis info
        redis_info = await redis_client.info()

        return {
            'status': 'healthy',
            'process': process_info,
            'redis': {
                'connected_clients': redis_info.get('connected_clients', 0),
                'used_memory': redis_info.get('used_memory_human', 'N/A'),
                'uptime': redis_info.get('uptime_in_seconds', 0)
            }
        }
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


@app.get('/api/websocket/connections')
async def get_websocket_connections():
    """Get all active WebSocket connections across all processes"""
    if not manager:
        return {'connections': []}

    try:
        redis_client = await manager.get_redis()
        connection_keys = await redis_client.keys('websocket:connections:*')

        connections = []
        for key in connection_keys:
            try:
                client_id = key.split(':')[-1]
                connection_data = await redis_client.hgetall(key)
                if connection_data:
                    connections.append({
                        'client_id': client_id,
                        'process_id': connection_data.get('process_id'),
                        'connected_at': connection_data.get('connected_at'),
                        'last_heartbeat': connection_data.get('last_heartbeat')
                    })
            except Exception as e:
                print(f"Error getting connection data for {key}: {e}")

        return {'connections': connections}
    except Exception as e:
        return {'error': str(e), 'connections': []}


@app.post('/api/websocket/broadcast')
async def broadcast_message(message: str):
    """Broadcast a message to all WebSocket clients"""
    if not manager:
        return {'error': 'WebSocket service not available'}

    try:
        await manager.broadcast_to_all_processes(message)
        return {'status': 'success', 'message': 'Message broadcasted'}
    except Exception as e:
        return {'error': str(e)}


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time communication"""
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
            'message': 'Connected to WebSocket service'
        }))

        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                if message.get('type') == 'subscribe':
                    symbol = message.get('symbol')
                    if symbol:
                        await manager.subscribe_symbol(symbol)
                        await websocket.send_text(json.dumps({
                            'type': 'subscribed',
                            'symbol': symbol,
                            'timestamp': datetime.now().isoformat()
                        }))
                        print(f"Subscribed {client_id} to {symbol}")

                        # Send initial quote data
                        try:
                            redis_client = await manager.get_redis()
                            quote_key = f"quote:{symbol}"
                            cached_quote = await redis_client.get(quote_key)

                            if cached_quote:
                                quote_data = json.loads(cached_quote)
                            else:
                                # Generate mock quote for testing
                                quote_data = {
                                    'symbol': symbol,
                                    'price': 150.0,
                                    'change': 1.5,
                                    'changePercent': 1.0,
                                    'volume': 1000000,
                                    'marketCap': 2500000000000,
                                    'timestamp': datetime.now().isoformat()
                                }
                                # Cache the mock quote
                                await redis_client.setex(quote_key, 60, json.dumps(quote_data))

                            await websocket.send_text(json.dumps({
                                'type': 'quote',
                                'data': quote_data,
                                'timestamp': datetime.now().isoformat()
                            }))
                        except Exception as e:
                            print(
                                f"Error sending initial quote for {symbol}: {e}")

                elif message.get('type') == 'unsubscribe':
                    symbol = message.get('symbol')
                    if symbol:
                        # Note: We'll implement proper unsubscribe logic later
                        await websocket.send_text(json.dumps({
                            'type': 'unsubscribed',
                            'symbol': symbol,
                            'timestamp': datetime.now().isoformat()
                        }))
                        print(f"Unsubscribed {client_id} from {symbol}")

                elif message.get('type') == 'get_quote':
                    symbol = message.get('symbol')
                    if not symbol:
                        await websocket.send_text(json.dumps({
                            'type': 'error',
                            'message': 'Symbol is required for quote request'
                        }))
                        continue

                    # Get quote from Redis cache or generate mock
                    try:
                        redis_client = await manager.get_redis()
                        quote_key = f"quote:{symbol}"
                        cached_quote = await redis_client.get(quote_key)

                        if cached_quote:
                            quote_data = json.loads(cached_quote)
                            await websocket.send_text(json.dumps({
                                'type': 'quote',
                                'data': quote_data,
                                'timestamp': datetime.now().isoformat()
                            }))
                        else:
                            # Send a mock quote for testing
                            mock_quote = {
                                'symbol': symbol,
                                'price': 150.0,
                                'change': 1.5,
                                'changePercent': 1.0,
                                'volume': 1000000,
                                'timestamp': datetime.now().isoformat()
                            }
                            # Cache the mock quote
                            await redis_client.setex(quote_key, 60, json.dumps(mock_quote))
                            await websocket.send_text(json.dumps({
                                'type': 'quote',
                                'data': mock_quote,
                                'timestamp': datetime.now().isoformat()
                            }))
                    except Exception as e:
                        print(f"Error getting quote for {symbol}: {e}")
                        await websocket.send_text(json.dumps({
                            'type': 'error',
                            'message': f'Error getting quote: {str(e)}'
                        }))

                elif message.get('type') == 'ping':
                    # Handle ping/pong for connection health
                    await websocket.send_text(json.dumps({
                        'type': 'pong',
                        'timestamp': datetime.now().isoformat()
                    }))

                elif message.get('type') == 'broadcast':
                    # Allow clients to broadcast messages to all other clients
                    broadcast_message = message.get('message', '')
                    if broadcast_message:
                        await manager.broadcast_to_all_processes(broadcast_message)
                        await websocket.send_text(json.dumps({
                            'type': 'broadcast_sent',
                            'message': broadcast_message,
                            'timestamp': datetime.now().isoformat()
                        }))

                else:
                    await websocket.send_text(json.dumps({
                        'type': 'error',
                        'message': f'Unknown message type: {message.get("type")}'
                    }))

            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    'type': 'error',
                    'message': 'Invalid JSON format'
                }))
            except Exception as e:
                print(f"Error processing message from {client_id}: {e}")
                await websocket.send_text(json.dumps({
                    'type': 'error',
                    'message': f'Internal server error: {str(e)}'
                }))

    except WebSocketDisconnect:
        if manager:
            await manager.disconnect(websocket, client_id)
        print(f"WebSocket client disconnected: {client_id}")
    except Exception as e:
        print(f"WebSocket error for {client_id}: {e}")
        if manager:
            await manager.disconnect(websocket, client_id)
        try:
            await websocket.close(code=1011, reason="Internal error")
        except:
            pass

# Background task to simulate real-time quote updates


async def simulate_quote_updates():
    """Simulate real-time quote updates for subscribed symbols"""
    while True:
        try:
            if manager:
                redis_client = await manager.get_redis()
                subscribed_symbols = await redis_client.smembers('websocket:subscribed_symbols')

                for symbol in subscribed_symbols:
                    symbol_str = symbol.decode(
                        'utf-8') if isinstance(symbol, bytes) else symbol

                    # Generate simulated price movement
                    quote_key = f"quote:{symbol_str}"
                    cached_quote = await redis_client.get(quote_key)

                    if cached_quote:
                        current_quote = json.loads(cached_quote)

                        # Simulate price movement (±2% max)
                        price_change = current_quote['price'] * \
                            (random.uniform(-0.02, 0.02))
                        new_price = current_quote['price'] + price_change
                        new_change = current_quote['change'] + price_change
                        new_change_percent = (
                            new_change / (new_price - new_change)) * 100

                        updated_quote = {
                            'symbol': symbol_str,
                            'price': round(new_price, 2),
                            'change': round(new_change, 2),
                            'changePercent': round(new_change_percent, 2),
                            'volume': current_quote['volume'] + random.randint(-10000, 10000),
                            'marketCap': current_quote['marketCap'],
                            'timestamp': datetime.now().isoformat()
                        }

                        # Update cache
                        await redis_client.setex(quote_key, 60, json.dumps(updated_quote))

                        # Broadcast to all connected clients
                        await manager.broadcast(json.dumps({
                            'type': 'quote',
                            'data': updated_quote,
                            'timestamp': datetime.now().isoformat()
                        }))

            await asyncio.sleep(2)  # Update every 2 seconds

        except Exception as e:
            print(f"Error in quote updates simulation: {e}")
            await asyncio.sleep(5)  # Wait longer on error


@app.get('/api/realtime/quote/{symbol}')
async def get_realtime_quote(symbol: str):
    """Get real-time quote for a symbol"""
    try:
        # Sanitize symbol (remove leading $ or other non-alphanumerics except . and =)
        clean_symbol = ''.join(
            ch for ch in symbol if ch.isalnum() or ch in ['.', '='])
        ticker = yf.Ticker(clean_symbol)
        info = ticker.info
        quote = {
            'symbol': clean_symbol,
            'price': info.get('regularMarketPrice', 0),
            'change': info.get('regularMarketChange', 0),
            'changePercent': info.get('regularMarketChangePercent', 0),
            'volume': info.get('volume', 0),
            'marketCap': info.get('marketCap', 0),
            'timestamp': datetime.now().isoformat()
        }
        return quote
    except Exception as e:
        return {'error': str(e)}


@app.get('/api/bars/{symbol}/{interval}')
async def get_bars(symbol: str, interval: str = '1m', period: str = '1d'):
    """Get bar data for a symbol with specified interval"""
    try:
        # Sanitize symbol
        clean_symbol = ''.join(
            ch for ch in symbol if ch.isalnum() or ch in ['.', '='])
        # Validate interval
        allowed_intervals = {
            '1m', '5m', '15m', '30m', '65m',
            '1d', '1wk', '1mo', '3mo'
        }
        if interval not in allowed_intervals:
            return {'error': f'Invalid interval: {interval}'}

        hist = BarsManager.get_instance().get_bars(clean_symbol, interval, period)
        if hist.empty:
            return {'error': 'No data available'}

        # Convert to OHLCV format
        bars = []
        for index, row in hist.iterrows():
            bars.append({
                # Convert to milliseconds
                'timestamp': int(index.timestamp() * 1000),
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': int(row['Volume'])
            })

        return {
            'symbol': clean_symbol,
            'interval': interval,
            'bars': bars
        }
    except Exception as e:
        return {'error': str(e)}


@app.get('/update_us_trade_calendar')
async def update_us_trade_calendar() -> str:
    update_us_trade_calendar_task.delay()
    return 'GOOD'


@app.get('/update_spx_tickers_info')
async def update_spx_tickers_info() -> str:
    chain(update_spx_tickers_task.si(), update_spx_tickers_info_task.si())()
    return 'GOOD'


@app.get('/update_iwd_tickers_info')
async def update_iwf_tickers_info() -> str:
    chain(update_iwd_tickers_task.si(), update_iwd_tickers_info_task.si())()
    return 'GOOD'


@app.get('/update_iwf_tickers_info')
async def update_iwf_tickers_info() -> str:
    chain(update_iwf_tickers_task.si(), update_iwf_tickers_info_task.si())()
    return 'GOOD'


@app.get('/update_iwm_tickers_info')
async def update_iwm_tickers_info() -> str:
    chain(update_iwm_tickers_task.si(), update_iwm_tickers_info_task.si())()
    return 'GOOD'


@app.get('/update_spx_tickers_daily_info')
async def update_spx_tickers_daily_info() -> str:
    update_spx_tickers_daily_info_task.delay()
    return 'GOOD'


@app.get('/update_iwd_tickers_daily_info')
async def update_iwd_tickers_daily_info() -> str:
    update_iwd_tickers_daily_info_task.delay()
    return 'GOOD'


@app.get('/update_iwf_tickers_daily_info')
async def update_iwf_tickers_daily_info() -> str:
    update_iwf_tickers_daily_info_task.delay()
    return 'GOOD'


@app.get('/update_iwm_tickers_daily_info')
async def update_iwm_tickers_daily_info() -> str:
    update_iwm_tickers_daily_info_task.delay()
    return 'GOOD'


@app.post('/update_tickers_daily_info')
async def update_tickers_daily_info(tickers: List[str]) -> str:
    update_tickers_daily_info_task.delay(tickers=tickers)
    return 'GOOD'


@app.get('/update_spx_daily_ma')
async def update_spx_daily_ma() -> str:
    update_spx_daily_ma_task.delay()
    return 'GOOD'


@app.get('/update_iw_daily_ma')
async def update_iw_daily_ma() -> str:
    update_iw_daily_ma_task.delay()
    return 'GOOD'


@app.get('/update_market_pe')
async def update_market_pe() -> str:
    update_market_pe_task.delay()
    return 'GOOD'


@app.get('/update_spx_market_breadth')
async def update_spx_market_breadth() -> str:
    update_spx_market_breadth_task.delay()
    return 'GOOD'


@app.get('/update_wedge_pop_for_index')
async def update_wedge_pop_for_index() -> str:
    update_wedge_pop_for_index_task.delay()
    return 'GOOD'


@app.get('/run_us_daily_updates', description='Update US daily data')
async def run_us_daily_updates() -> str:
    run_us_daily_updates_task.delay()
    return 'GOOD'


@app.get('/run_hk_daily_updates')
async def update_hk_daily_updates() -> str:
    run_hk_daily_updates_task.delay()
    return 'GOOD'


@app.post('/update_indicators_for_tickers')
async def update_indicators_for_tickers(tickers: List[str]) -> str:
    update_indicators_for_tickers_task.delay(tickers=tickers)
    return 'GOOD'


@app.get('/api/mbs/{market_index}.json')
async def get_mbs(market_index: str = 'spx', start_date: str = None, end_date: str = None) -> list | dict:
    '''
    获取市场宽度分数
    :return:
    '''
    make_db_connection()
    return MarketBreadth.get_instance().get_market_breath(market_index=market_index, start_date=start_date,
                                                          end_date=end_date).dropna().drop(columns=['_id']).to_dict(orient='records')


@app.get('/api/market_pe/{index}.json')
async def get_market_pe(index: str = 'spx', start_date: str = None, end_date: str = None) -> dict:
    '''
    Get market PE data for visualization
    :param index: 'spx' or 'qqq'
    :param start_date: start date in YYYY-MM-DD format (optional)
    :param end_date: end date in YYYY-MM-DD format (optional)
    :return: dict with PE data and statistics
    '''
    make_db_connection()

    # Set default date range if not provided
    if not end_date:
        end_date = datetime.now(tz=pytz.timezone(
            'America/New_York')).strftime('%Y-%m-%d')
    if not start_date:
        # Default to 20 years ago
        start_date = (datetime.now(tz=pytz.timezone('America/New_York')
                                   ) - timedelta(days=365*20)).strftime('%Y-%m-%d')

    # Convert dates to datetime objects for querying
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')

    # Query the database
    query = {
        'idx': index,
        'trade_date__gte': start_dt,
        'trade_date__lte': end_dt
    }

    df = mongo_2_df(MarketPe.objects(**query).order_by('trade_date'))

    if df.empty:
        return {
            'index': index,
            'data': [],
            'stats': {
                'avg_20y': 0,
                'current_pe': 0,
                'min_pe': 0,
                'max_pe': 0
            }
        }

    # Convert to Highcharts format [timestamp, pe_value]
    data = []
    for _, row in df.iterrows():
        # Handle trade_date which might be a string from mongo_2_df
        if isinstance(row['trade_date'], str):
            # Parse the string date format from MongoDB
            # The scraper stores dates in format "2024,01,15,00,00,00,000000"
            try:
                # Try to parse the custom format used by the scraper
                dt = datetime.strptime(
                    row['trade_date'], '%Y,%m,%d,%H,%M,%S,%f')
            except ValueError:
                try:
                    # Try to parse ISO format as fallback
                    dt = datetime.fromisoformat(
                        row['trade_date'].replace('Z', '+00:00'))
                except ValueError:
                    # Fallback to other common formats
                    dt = datetime.strptime(
                        row['trade_date'], '%Y-%m-%d %H:%M:%S')
        else:
            # If it's already a datetime object
            dt = row['trade_date']

        timestamp = int(dt.timestamp() * 1000)  # Convert to milliseconds
        data.append([timestamp, float(row['pe'])])

    # Calculate statistics
    pe_values = df['pe'].values
    avg_20y = float(pe_values.mean())
    current_pe = float(pe_values[-1]) if len(pe_values) > 0 else 0
    min_pe = float(pe_values.min())
    max_pe = float(pe_values.max())

    return {
        'index': index,
        'data': data,
        'stats': {
            'avg_20y': avg_20y,
            'current_pe': current_pe,
            'min_pe': min_pe,
            'max_pe': max_pe
        }
    }


@app.get('/api/wedge_pop/latest.json', description='Get all wedge pop tickers of today')
async def get_wedge_pop_tickers_of_today() -> dict | list:
    wedge_pop: WedgePop = WedgePop.get_instance()
    return wedge_pop.get_wedge_tickers_on_today()


@app.get('/api/wedge_pop/wedges.json', description='Get wedge pop tickers since 1 year ago')
async def get_wedge_pop_tickers() -> dict | list:
    wedge_pop: WedgePop = WedgePop.get_instance()
    start_date = datetime.now(tz=pytz.timezone(
        'America/New_York')) - timedelta(days=365)
    return wedge_pop.get_wedge_tickers_since(start_date)


@app.get('/api/wedge_pop/stats.json', description='Get wedge pop stats')
async def get_wedge_pop_stats(start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict | list:
    wedge_pop: WedgePop = WedgePop.get_instance()
    return wedge_pop.get_wedge_stats(start_date=start_date, end_date=end_date)


@app.get('/api/ohlcvw/{ticker}.json', description='Get OHLCVW data for a ticker, default to 3 years ago')
async def get_ohlcvw(ticker: str, start_date: Optional[str] = None, end_date: Optional[str] = None, interval: str = '1d') -> dict | list[Any]:
    md: MarketDataShovel = MarketDataShovel.get_instance()
    if start_date is None:
        start_date = datetime.now(tz=pytz.timezone(
            'America/New_York')) - timedelta(days=365*3)
    if end_date is None:
        end_date = datetime.now(tz=pytz.timezone(
            'America/New_York'))
    dailies_df = md.get_ticker_daily_info(
        ticker, start_date, end_date, interval=interval)
    dailies_df = dailies_df[['trade_date', 'ticker', 'open',
                             'high', 'low', 'close', 'volume', 'wedge_status']]
    return dailies_df.to_dict(orient='records')


# Watchlist endpoints
@app.get('/api/watchlist')
async def get_watchlist() -> dict:
    """Get the current watchlist"""
    try:
        # For now, we'll use a simple file-based storage
        # In production, you might want to use a database
        watchlist_file = 'watchlist.json'
        if os.path.exists(watchlist_file):
            with open(watchlist_file, 'r') as f:
                watchlist = json.load(f)
        else:
            watchlist = []
        return {'watchlist': watchlist}
    except Exception as e:
        return {'error': str(e), 'watchlist': []}


@app.post('/api/watchlist')
async def add_to_watchlist(ticker: str) -> dict:
    """Add a ticker to the watchlist"""
    try:
        watchlist_file = 'watchlist.json'
        watchlist = []

        if os.path.exists(watchlist_file):
            with open(watchlist_file, 'r') as f:
                watchlist = json.load(f)

        # Check if ticker already exists
        if ticker.upper() not in [item['ticker'] for item in watchlist]:
            watchlist.append({
                'ticker': ticker.upper(),
                'added_at': datetime.now().isoformat()
            })

            with open(watchlist_file, 'w') as f:
                json.dump(watchlist, f, indent=2)

            return {'status': 'success', 'message': f'{ticker.upper()} added to watchlist'}
        else:
            return {'status': 'error', 'message': f'{ticker.upper()} already in watchlist'}

    except Exception as e:
        return {'status': 'error', 'message': str(e)}


@app.delete('/api/watchlist/{ticker}')
async def remove_from_watchlist(ticker: str) -> dict:
    """Remove a ticker from the watchlist"""
    try:
        watchlist_file = 'watchlist.json'
        if not os.path.exists(watchlist_file):
            return {'status': 'error', 'message': 'Watchlist not found'}

        with open(watchlist_file, 'r') as f:
            watchlist = json.load(f)

        # Remove the ticker
        original_length = len(watchlist)
        watchlist = [
            item for item in watchlist if item['ticker'] != ticker.upper()]

        if len(watchlist) < original_length:
            with open(watchlist_file, 'w') as f:
                json.dump(watchlist, f, indent=2)
            return {'status': 'success', 'message': f'{ticker.upper()} removed from watchlist'}
        else:
            return {'status': 'error', 'message': f'{ticker.upper()} not found in watchlist'}

    except Exception as e:
        return {'status': 'error', 'message': str(e)}
