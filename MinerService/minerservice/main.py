import asyncio
import json
import math
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

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

# WebSocket connection manager with Redis support and bars broadcasting


class RedisConnectionManager:
    def __init__(self):
        self.redis_client = None
        self.process_id = str(uuid.uuid4())
        self.local_connections: Dict[str, WebSocket] = {}
        self.subscribed_symbols: Set[str] = set()
        # bars subscriptions: key is (symbol, interval)
        self.subscribed_bars: Set[Tuple[str, str]] = set()
        # last sent bar timestamp (ms) per (symbol, interval)
        self.last_bars_ts: Dict[Tuple[str, str], int] = {}
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

    async def subscribe_bars(self, symbol: str, interval: str):
        key = (symbol.upper(), interval)
        if key not in self.subscribed_bars:
            self.subscribed_bars.add(key)
            try:
                # Store subscription in Redis
                redis_client = await self.get_redis()
                await redis_client.sadd('websocket:subscribed_bars', f"{key[0]}|{key[1]}")
                print(f"Subscribed to bars: {key[0]} {key[1]}")
            except Exception as e:
                print(f"Error subscribing to bars {key}: {e}")

    async def unsubscribe_bars(self, symbol: str, interval: str):
        key = (symbol.upper(), interval)
        if key in self.subscribed_bars:
            self.subscribed_bars.remove(key)
            try:
                redis_client = await self.get_redis()
                await redis_client.srem('websocket:subscribed_bars', f"{key[0]}|{key[1]}")
            except Exception:
                pass

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
                                # Get real quote data from yfinance
                                try:
                                    clean_symbol = ''.join(
                                        ch for ch in symbol if ch.isalnum() or ch in ['.', '='])
                                    ticker = yf.Ticker(clean_symbol)
                                    info = ticker.info

                                    quote_data = {
                                        'symbol': clean_symbol,
                                        'price': info.get('regularMarketPrice', 0),
                                        'change': info.get('regularMarketChange', 0),
                                        'changePercent': info.get('regularMarketChangePercent', 0),
                                        'volume': info.get('volume', 0),
                                        'marketCap': info.get('marketCap', 0),
                                        'timestamp': datetime.now().isoformat()
                                    }

                                    # Cache the real quote data
                                    await redis_client.setex(quote_key, 60, json.dumps(quote_data))
                                    print(
                                        f"Fetched real quote for {symbol}: ${quote_data['price']}")
                                except Exception as e:
                                    print(
                                        f"Error fetching real quote for {symbol}: {e}")
                                    # Fallback to a default quote structure
                                    quote_data = {
                                        'symbol': symbol,
                                        'price': 0,
                                        'change': 0,
                                        'changePercent': 0,
                                        'volume': 0,
                                        'marketCap': 0,
                                        'timestamp': datetime.now().isoformat()
                                    }

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

                    # Get quote from Redis cache or fetch real data
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
                            # Get real quote data from yfinance
                            try:
                                clean_symbol = ''.join(
                                    ch for ch in symbol if ch.isalnum() or ch in ['.', '='])
                                ticker = yf.Ticker(clean_symbol)
                                info = ticker.info

                                quote_data = {
                                    'symbol': clean_symbol,
                                    'price': info.get('regularMarketPrice', 0),
                                    'change': info.get('regularMarketChange', 0),
                                    'changePercent': info.get('regularMarketChangePercent', 0),
                                    'volume': info.get('volume', 0),
                                    'marketCap': info.get('marketCap', 0),
                                    'timestamp': datetime.now().isoformat()
                                }

                                # Cache the real quote data
                                await redis_client.setex(quote_key, 60, json.dumps(quote_data))
                                print(
                                    f"Fetched real quote for {symbol}: ${quote_data['price']}")
                            except Exception as e:
                                print(
                                    f"Error fetching real quote for {symbol}: {e}")
                                # Fallback to a default quote structure
                                quote_data = {
                                    'symbol': symbol,
                                    'price': 0,
                                    'change': 0,
                                    'changePercent': 0,
                                    'volume': 0,
                                    'marketCap': 0,
                                    'timestamp': datetime.now().isoformat()
                                }

                            await websocket.send_text(json.dumps({
                                'type': 'quote',
                                'data': quote_data,
                                'timestamp': datetime.now().isoformat()
                            }))
                    except Exception as e:
                        print(f"Error getting quote for {symbol}: {e}")
                        await websocket.send_text(json.dumps({
                            'type': 'error',
                            'message': f'Error getting quote: {str(e)}'
                        }))

                elif message.get('type') == 'subscribe_bars':
                    symbol = message.get('symbol')
                    interval = message.get('interval')
                    if symbol and interval:
                        print(
                            f"Client {client_id} subscribing to bars: {symbol} {interval}")
                        await manager.subscribe_bars(symbol, interval)
                        await websocket.send_text(json.dumps({
                            'type': 'subscribed_bars',
                            'symbol': symbol,
                            'interval': interval,
                            'timestamp': datetime.now().isoformat()
                        }))

                        # Immediately send initial bars snapshot
                        try:
                            # Get full bars for initial snapshot using get_bars
                            hist = BarsManager.get_instance().get_bars(symbol, interval, 'max')
                            if not hist.empty:
                                bars = []
                                for index, row in hist.iterrows():
                                    bars.append({
                                        'timestamp': int(index.timestamp() * 1000),
                                        'open': float(row['Open']),
                                        'high': float(row['High']),
                                        'low': float(row['Low']),
                                        'close': float(row['Close']),
                                        'volume': int(row['Volume'])
                                    })

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

                                # Store the last timestamp for this stream
                                if bars:
                                    last_ts = bars[-1]['timestamp']
                                    manager.last_bars_ts[(
                                        symbol.upper(), interval)] = last_ts
                                    print(
                                        f"Stored last timestamp for {symbol} {interval}: {last_ts}")

                        except Exception as e:
                            print(
                                f"Error sending initial bars for {symbol} {interval}: {e}")

                elif message.get('type') == 'unsubscribe_bars':
                    symbol = message.get('symbol')
                    interval = message.get('interval')
                    if symbol and interval:
                        await manager.unsubscribe_bars(symbol, interval)
                        await websocket.send_text(json.dumps({
                            'type': 'unsubscribed_bars',
                            'symbol': symbol,
                            'interval': interval,
                            'timestamp': datetime.now().isoformat()
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

# Background task for real-time bars updates


async def monitor_bars_updates():
    """Monitor and broadcast real-time bars updates for subscribed symbols"""
    print("Starting bars monitoring service...")
    while True:
        try:
            if manager:
                redis_client = await manager.get_redis()
                subscribed_bars = await redis_client.smembers('websocket:subscribed_bars')

                if subscribed_bars:
                    print(
                        f"Monitoring {len(subscribed_bars)} bars subscriptions: {[key.decode('utf-8') if isinstance(key, bytes) else key for key in subscribed_bars]}")
                else:
                    print("No bars subscriptions to monitor")

                for key in subscribed_bars:
                    try:
                        key_str = key.decode(
                            'utf-8') if isinstance(key, bytes) else key
                        sym, interval = key_str.split('|')

                        print(f"Checking bars for {sym} {interval}...")

                        # Get recent bars for comparison
                        hist = BarsManager.get_instance().get_recent_bars(sym, interval, 10)
                        if hist.empty:
                            print(f"No bars data for {sym} {interval}")
                            continue

                        print(
                            f"Got {len(hist)} recent bars for {sym} {interval}")

                        # Get the latest bar
                        last_row = hist.iloc[-1]
                        last_idx = hist.index[-1]

                        # Debug: Show the actual data we're getting
                        print(f"Latest bar data for {sym} {interval}:")
                        print(f"  Index: {last_idx}")
                        print(f"  Open: {last_row['Open']}")
                        print(f"  High: {last_row['High']}")
                        print(f"  Low: {last_row['Low']}")
                        print(f"  Close: {last_row['Close']}")
                        print(f"  Volume: {last_row['Volume']}")

                        # Check if this is the same data as last time we checked
                        current_data_hash = hash(
                            f"{last_row['Open']}{last_row['High']}{last_row['Low']}{last_row['Close']}{last_row['Volume']}")
                        last_check_hash_key = f"bars:{sym}:{interval}:last_check_hash"
                        last_check_hash = await redis_client.get(last_check_hash_key)

                        if last_check_hash and int(last_check_hash) == current_data_hash:
                            print(
                                f"Data unchanged from last check for {sym} {interval} - skipping entire check")
                            continue
                        else:
                            # Store the new hash for next comparison
                            await redis_client.setex(last_check_hash_key, 60, str(current_data_hash))
                            print(
                                f"Data changed from last check for {sym} {interval} - proceeding with update check")

                        last_ts_ms = int(last_idx.timestamp() * 1000)
                        prev_ts_ms = manager.last_bars_ts.get((sym, interval))

                        # Check if the bar is too old (market closed)
                        current_time = datetime.now()
                        bar_time = datetime.fromtimestamp(last_idx.timestamp())
                        time_diff = current_time - bar_time

                        # Skip if bar is older than 1 hour for minute intervals, 1 day for others
                        max_age_hours = 1 if interval in [
                            '1m', '5m', '15m', '30m', '60m', '65m'] else 24
                        if time_diff.total_seconds() > max_age_hours * 3600:
                            print(
                                f"Bar too old for {sym} {interval}: {time_diff.total_seconds()/3600:.1f} hours, skipping")
                            continue

                        print(
                            f"Latest bar timestamp: {last_ts_ms}, Previous: {prev_ts_ms}, Age: {time_diff.total_seconds()/60:.1f} minutes")

                        # Check if we have new data to send
                        bars = []

                        if prev_ts_ms is None:
                            # First time - don't send anything, just store timestamp
                            # The initial snapshot was already sent during subscription
                            manager.last_bars_ts[(sym, interval)] = last_ts_ms
                            print(
                                f"Initial timestamp stored for {sym} {interval}: {last_ts_ms}")

                            # Cache current data for future comparison
                            current_data = {
                                'open': float(last_row['Open']),
                                'high': float(last_row['High']),
                                'low': float(last_row['Low']),
                                'close': float(last_row['Close']),
                                'volume': int(last_row['Volume'])
                            }
                            prev_data_key = f"bars:{sym}:{interval}:{last_ts_ms}"
                            await redis_client.setex(prev_data_key, 300, json.dumps(current_data))

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
                            manager.last_bars_ts[(sym, interval)] = last_ts_ms
                            print(
                                f"New incremental bar sent for {sym} {interval}: {last_ts_ms}")

                            # Cache current data for future comparison
                            current_data = {
                                'open': float(last_row['Open']),
                                'high': float(last_row['High']),
                                'low': float(last_row['Low']),
                                'close': float(last_row['Close']),
                                'volume': int(last_row['Volume'])
                            }
                            prev_data_key = f"bars:{sym}:{interval}:{last_ts_ms}"
                            await redis_client.setex(prev_data_key, 300, json.dumps(current_data))

                        elif last_ts_ms == prev_ts_ms:
                            # Same timestamp - check if data actually changed (for forming bars)
                            current_data = {
                                'open': float(last_row['Open']),
                                'high': float(last_row['High']),
                                'low': float(last_row['Low']),
                                'close': float(last_row['Close']),
                                'volume': int(last_row['Volume'])
                            }

                            # Get previous data from cache to compare
                            prev_data_key = f"bars:{sym}:{interval}:{prev_ts_ms}"
                            prev_data_str = await redis_client.get(prev_data_key)

                            if prev_data_str:
                                prev_data = json.loads(prev_data_str)

                                # Check if data actually changed
                                data_changed = False
                                if (abs(current_data['high'] - prev_data['high']) > 0.001 or
                                    abs(current_data['low'] - prev_data['low']) > 0.001 or
                                    abs(current_data['close'] - prev_data['close']) > 0.001 or
                                        abs(current_data['volume'] - prev_data['volume']) > 0):
                                    data_changed = True

                                print(f"Data comparison for {sym} {interval}:")
                                print(
                                    f"  Current: O:{current_data['open']:.4f} H:{current_data['high']:.4f} L:{current_data['low']:.4f} C:{current_data['close']:.4f} V:{current_data['volume']}")
                                print(
                                    f"  Previous: O:{prev_data['open']:.4f} H:{prev_data['high']:.4f} L:{prev_data['low']:.4f} C:{prev_data['close']:.4f} V:{prev_data['volume']}")
                                print(f"  Data changed: {data_changed}")

                                if data_changed:
                                    # Check if we already sent this exact data recently
                                    data_hash = hash(
                                        f"{current_data['open']:.4f}{current_data['high']:.4f}{current_data['low']:.4f}{current_data['close']:.4f}{current_data['volume']}")
                                    last_sent_hash_key = f"bars:{sym}:{interval}:{prev_ts_ms}:hash"
                                    last_sent_hash = await redis_client.get(last_sent_hash_key)

                                    if last_sent_hash and int(last_sent_hash) == data_hash:
                                        print(
                                            f"Data already sent for {sym} {interval} - skipping duplicate")
                                    else:
                                        # Data changed and not duplicate, send incremental update
                                        bars.append({
                                            'timestamp': last_ts_ms,
                                            **current_data
                                        })
                                        print(
                                            f"Forming bar update sent for {sym} {interval} - data changed")

                                        # Store the hash to prevent duplicates
                                        await redis_client.setex(last_sent_hash_key, 300, str(data_hash))
                                else:
                                    print(
                                        f"No meaningful change for {sym} {interval} - skipping update")
                            else:
                                # No previous data to compare, cache current data
                                await redis_client.setex(prev_data_key, 300, json.dumps(current_data))
                                print(
                                    f"Cached data for {sym} {interval} - no previous data to compare")

                        # Broadcast bars if we have updates
                        if bars:
                            print(
                                f"Broadcasting {len(bars)} incremental bars for {sym} {interval}")
                            await manager.broadcast(json.dumps({
                                'type': 'bars',
                                'data': {
                                    'symbol': sym,
                                    'interval': interval,
                                    'bars': bars,
                                    'is_snapshot': False
                                },
                                'timestamp': datetime.now().isoformat()
                            }))
                        else:
                            print(
                                f"No incremental bars to broadcast for {sym} {interval}")

                    except Exception as e:
                        print(f"Error processing bars update for {key}: {e}")

            # Wait before next check - adjust based on interval types
            await asyncio.sleep(5)  # Check every 5 seconds

        except Exception as e:
            print(f"Error in bars monitoring: {e}")
            await asyncio.sleep(10)  # Wait longer on error


# Background task to simulate real-time quote updates (keeping this for now)
async def update_real_quotes():
    """Fetch and broadcast real-time quote updates for subscribed symbols"""
    while True:
        try:
            if manager:
                redis_client = await manager.get_redis()
                subscribed_symbols = await redis_client.smembers('websocket:subscribed_symbols')

                for symbol in subscribed_symbols:
                    symbol_str = symbol.decode(
                        'utf-8') if isinstance(symbol, bytes) else symbol

                    try:
                        # Fetch real quote data from yfinance
                        clean_symbol = ''.join(
                            ch for ch in symbol_str if ch.isalnum() or ch in ['.', '='])
                        ticker = yf.Ticker(clean_symbol)
                        info = ticker.info

                        # Get current cached quote for comparison
                        quote_key = f"quote:{symbol_str}"
                        cached_quote = await redis_client.get(quote_key)

                        if cached_quote:
                            current_quote = json.loads(cached_quote)
                            current_price = current_quote.get('price', 0)
                        else:
                            current_price = 0

                        # Fetch new quote data
                        new_price = info.get('regularMarketPrice', 0)
                        new_change = info.get('regularMarketChange', 0)
                        new_change_percent = info.get(
                            'regularMarketChangePercent', 0)
                        new_volume = info.get('volume', 0)
                        new_market_cap = info.get('marketCap', 0)

                        # Only update if price actually changed (avoid unnecessary broadcasts)
                        if abs(new_price - current_price) > 0.001:
                            updated_quote = {
                                'symbol': clean_symbol,
                                'price': new_price,
                                'change': new_change,
                                'changePercent': new_change_percent,
                                'volume': new_volume,
                                'marketCap': new_market_cap,
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

                            print(
                                f"Updated real quote for {symbol_str}: ${new_price} (change: {new_change:+.2f})")
                        else:
                            # Update cache with current data even if price didn't change
                            # This ensures we have fresh volume and other data
                            updated_quote = {
                                'symbol': clean_symbol,
                                'price': new_price,
                                'change': new_change,
                                'changePercent': new_change_percent,
                                'volume': new_volume,
                                'marketCap': new_market_cap,
                                'timestamp': datetime.now().isoformat()
                            }
                            await redis_client.setex(quote_key, 60, json.dumps(updated_quote))

                    except Exception as e:
                        print(f"Error updating quote for {symbol_str}: {e}")
                        continue

            # Update quotes every 10 seconds (more reasonable for real market data)
            await asyncio.sleep(10)

        except Exception as e:
            print(f"Error in real quote updates: {e}")
            await asyncio.sleep(30)  # Wait longer on error


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

        # Convert to OHLCV format with safe handling of nan values
        bars = []
        for index, row in hist.iterrows():
            # Safely convert values, handling nan and inf
            try:
                open_price = float(row['Open']) if not math.isnan(
                    row['Open']) else 0.0
                high_price = float(row['High']) if not math.isnan(
                    row['High']) else 0.0
                low_price = float(row['Low']) if not math.isnan(
                    row['Low']) else 0.0
                close_price = float(row['Close']) if not math.isnan(
                    row['Close']) else 0.0
                volume = int(row['Volume']) if not math.isnan(
                    row['Volume']) else 0
            except (ValueError, TypeError):
                # Skip this row if conversion fails
                continue

            # Skip bars with invalid data (all zeros might indicate bad data)
            if all(price == 0.0 for price in [open_price, high_price, low_price, close_price]):
                continue

            bars.append({
                # Convert to milliseconds
                'timestamp': int(index.timestamp() * 1000),
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': volume
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
