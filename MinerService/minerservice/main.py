import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, List, Optional, Dict

import pytz
# yfinance import removed - using BarsManager integration only
from browserscraper.tasks import update_market_pe_task
from celery import chain
from dataminer import MarketDataShovel, WedgePop
from dataminer.models import MarketPe
from detonator import get_logger, make_db_connection, mongo_2_df
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
from .websocket.connection_manager import WebSocketConnectionManager

# Global manager instance
manager = None
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

# WebSocket connection manager with BarsManager integration
# Uses WebSocketConnectionManager from websocket/connection_manager.py


@app.get('/')
async def root():
    return {'Hello': 'World'}


@app.get('/api/websocket/status')
async def get_websocket_status():
    """Get WebSocket service status and connection information"""
    if not manager:
        return {'status': 'unavailable', 'message': 'WebSocket service not initialized'}

    try:
        # Get basic status
        status = {
            'status': 'healthy',
            'process': {
            'process_id': manager.process_id,
                'local_connections': len(manager.local_connections),
                'total_connections': await manager.get_total_connections(),
            'subscribed_symbols': list(manager.subscribed_symbols),
            'running': manager.running
            },
            'redis': await manager.get_redis_status()
        }

        # Add RedisSubscriptionService status if available
        if manager.redis_subscription_service:
            redis_service_status = {
                'running': manager.redis_subscription_service.running,
                'active_quote_subscriptions': list(manager.redis_subscription_service.active_quote_subscriptions),
                'active_bar_subscriptions': list(manager.redis_subscription_service.active_bar_subscriptions),
                'pubsub_ready': manager.redis_subscription_service.pubsub is not None
            }
            status['redis_subscription_service'] = redis_service_status

        return status

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
                        await manager.subscribe_symbol(symbol)
                        await websocket.send_text(json.dumps({
                            'type': 'subscribed',
                            'symbol': symbol,
                            'timestamp': datetime.now().isoformat()
                        }))
                        _logger.debug('Subscribed %s to %s', client_id, symbol)

                        # Send initial quote data via BarsManager integration
                        try:
                            if manager.bars_manager_integration:
                                quote_data = await manager.bars_manager_integration.get_initial_quote(symbol)
                                if quote_data:
                                    # Check if this is a placeholder for subscribed ticker
                                    if quote_data.get('status') == 'subscribed_waiting_for_data':
                                        await websocket.send_text(json.dumps({
                                            'type': 'subscribed',
                                            'symbol': symbol,
                                            'message': f'{symbol} subscribed to live quotes, waiting for data...',
                                            'timestamp': datetime.now().isoformat()
                                        }))
                                        print(f"Sent subscription confirmation for {symbol} (waiting for data)")
                                    else:
                                        await websocket.send_text(json.dumps({
                                            'type': 'quote',
                                            'data': quote_data,
                                            'timestamp': datetime.now().isoformat()
                                        }))
                                        print(f"Sent initial quote for {symbol} via BarsManager")
                                else:
                                    # Send error if no data available
                                    await websocket.send_text(json.dumps({
                                        'type': 'error',
                                        'message': f'No quote data available for {symbol}',
                                        'timestamp': datetime.now().isoformat()
                                    }))
                            else:
                                await websocket.send_text(json.dumps({
                                    'type': 'error',
                                    'message': 'BarsManager integration not available',
                                    'timestamp': datetime.now().isoformat()
                                }))
                        except Exception as e:
                            print(f"Error sending initial quote for {symbol}: {e}")
                            await websocket.send_text(json.dumps({
                                'type': 'error',
                                'message': f'Failed to get quote for {symbol}: {str(e)}',
                                'timestamp': datetime.now().isoformat()
                            }))
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
                    allowed_intervals = {'1m', '5m', '15m', '30m', '65m', '1d', '1wk', '1mo', '3mo'}
                    if interval not in allowed_intervals:
                        await websocket.send_text(json.dumps({
                            'type': 'error',
                            'message': f'Invalid interval: {interval}. Allowed: {", ".join(sorted(allowed_intervals))}',
                            'timestamp': datetime.now().isoformat()
                        }))
                        continue
                    
                    try:
                        await manager.subscribe_bars(symbol, interval)
                        await websocket.send_text(json.dumps({
                            'type': 'bars_subscribed',
                            'symbol': symbol,
                            'interval': interval,
                            'timestamp': datetime.now().isoformat()
                        }))
                        print(f"Subscribed {client_id} to {symbol} {interval} bars")

                        # Send initial bars data via BarsManager integration
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
                                    print(f"Sent initial bars for {symbol} {interval} via BarsManager")
                                else:
                                    await websocket.send_text(json.dumps({
                                        'type': 'error',
                                        'message': f'No bars data available for {symbol} {interval}',
                                        'timestamp': datetime.now().isoformat()
                                    }))
                            else:
                                await websocket.send_text(json.dumps({
                                    'type': 'error',
                                    'message': 'BarsManager integration not available',
                                    'timestamp': datetime.now().isoformat()
                                }))
                        except Exception as e:
                            print(f"Error sending initial bars for {symbol} {interval}: {e}")
                            await websocket.send_text(json.dumps({
                                'type': 'error',
                                'message': f'Failed to get bars for {symbol} {interval}: {str(e)}',
                                'timestamp': datetime.now().isoformat()
                            }))
                    except Exception as e:
                        print(f"Error subscribing to bars for {symbol} {interval}: {e}")
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
                        print(f"Unsubscribed {client_id} from {symbol} {interval} bars")
                    except Exception as e:
                        print(f"Error unsubscribing from bars for {symbol} {interval}: {e}")
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
        if manager:
            try:
                await manager.disconnect(websocket, client_id)
            except Exception as e:
                print(f"Error during disconnect cleanup for {client_id}: {e}")


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


@app.get('/api/realtime/quote/{symbol}')
async def get_realtime_quote(symbol: str):
    """Get real-time quote for a symbol via BarsManager"""
    try:
        # Sanitize symbol (remove leading $ or other non-alphanumerics except . and =)
        clean_symbol = ''.join(
            ch for ch in symbol if ch.isalnum() or ch in ['.', '='])

        # Get quote from BarsManager integration
        if manager and manager.bars_manager_integration:
            quote_data = await manager.bars_manager_integration.get_initial_quote(clean_symbol)
            if quote_data:
                return quote_data
            else:
                return {'error': f'No quote data available for {clean_symbol}'}
        else:
            return {'error': 'BarsManager integration not available'}

    except Exception as e:
        return {'error': f'Failed to fetch quote for {symbol}: {str(e)}'}


@app.get('/api/bars/{symbol}/{interval}')
async def get_bars(symbol: str, interval: str = '1m', period: str = '1d'):
    """Get bar data for a symbol with specified interval via BarsManager"""
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

        # Get bars from BarsManager integration
        if manager and manager.bars_manager_integration:
            bars_data = await manager.bars_manager_integration.get_initial_bars_snapshot(clean_symbol, interval)
            if bars_data:
                return {
                    'symbol': clean_symbol,
                    'interval': interval,
                    'bars': bars_data
                }
            else:
                return {'error': f'No bars data available for {clean_symbol} {interval}'}
        else:
            return {'error': 'BarsManager integration not available'}

    except Exception as e:
        return {'error': f'Failed to fetch bars for {symbol} {interval}: {str(e)}'}


@app.get('/update_us_trade_calendar')
async def update_us_trade_calendar() -> str:
    update_us_trade_calendar_task.delay()
    return 'GOOD'


@app.get('/update_spx_tickers_info')
async def update_spx_tickers_info() -> str:
    chain(update_spx_tickers_task.si(), update_spx_tickers_info_task.si())()
    return 'GOOD'


@app.get('/update_iwd_tickers_info')
async def update_iwd_tickers_info() -> str:
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


@app.get('/cleanup_subscriptions')
async def cleanup_subscriptions() -> Dict[str, Any]:
    """Clean up stale subscriptions and return status"""
    try:
        if manager:
            await manager.cleanup_stale_subscriptions()
            subscription_status = await manager.get_subscription_status()
            return {
                'status': 'success',
                'message': 'Subscription cleanup completed',
                'subscription_status': subscription_status
            }
        else:
            return {'error': 'Manager not available'}
    except Exception as e:
        return {'error': f'Failed to cleanup subscriptions: {str(e)}'}


@app.get('/test_quote_flow/{symbol}')
async def test_quote_flow(symbol: str) -> Dict[str, Any]:
    """Test the quote flow for a specific symbol"""
    try:
        if not manager:
            return {'error': 'Manager not available'}

        # Check if symbol is subscribed
        is_subscribed = symbol.upper() in manager.subscribed_symbols

        # Get subscription status
        subscription_status = await manager.get_subscription_status()

        # Check Redis for active quotes
        redis_client = await manager.get_redis()
        active_quotes = await redis_client.smembers('quotes:active')
        active_quotes = [
            q.decode('utf-8') if isinstance(q, bytes) else q for q in active_quotes]

        # Check if there are any recent quotes for this symbol
        latest_quote_key = f'quote:latest:{symbol.upper()}'
        latest_quote = await redis_client.get(latest_quote_key)

        # Get Redis subscription service health
        redis_service_health = None
        if manager.redis_subscription_service:
            redis_service_health = manager.redis_subscription_service.get_health_status()

        return {
            'symbol': symbol.upper(),
            'is_subscribed': is_subscribed,
            'subscription_status': subscription_status,
            'redis_service_health': redis_service_health,
            'active_quotes_in_redis': active_quotes,
            'latest_quote_available': latest_quote is not None,
            'latest_quote_data': latest_quote.decode('utf-8') if latest_quote else None
        }
    except Exception as e:
        return {'error': f'Failed to test quote flow: {str(e)}'}


@app.get('/redis_service_health')
async def redis_service_health() -> Dict[str, Any]:
    """Get health status of Redis subscription service"""
    try:
        if not manager or not manager.redis_subscription_service:
            return {'error': 'Redis subscription service not available'}

        health = manager.redis_subscription_service.get_health_status()
        return {
            'status': 'success',
            'health': health
        }
    except Exception as e:
        return {'error': f'Failed to get health status: {str(e)}'}


@app.post('/refresh_redis_subscriptions')
async def refresh_redis_subscriptions() -> Dict[str, Any]:
    """Manually refresh Redis subscriptions"""
    try:
        if not manager or not manager.redis_subscription_service:
            return {'error': 'Redis subscription service not available'}

        # Refresh subscriptions
        await manager.redis_subscription_service.refresh_subscriptions()

        # Get updated health status
        health = manager.redis_subscription_service.get_health_status()

        return {
            'status': 'success',
            'message': 'Redis subscriptions refreshed',
            'health': health
        }
    except Exception as e:
        return {'error': f'Failed to refresh subscriptions: {str(e)}'}


@app.post('/test_quote_flow_manual/{symbol}')
async def test_quote_flow_manual(symbol: str) -> Dict[str, Any]:
    """Manually test the complete quote flow for a symbol"""
    try:
        if not manager:
            return {'error': 'Manager not available'}

        # Step 1: Check if symbol is subscribed
        is_subscribed = symbol.upper() in manager.subscribed_symbols

        # Step 2: Check BarsManager subscription
        bars_manager_subscribed = False
        if manager.bars_manager_integration:
            bars_manager_subscribed = symbol.upper(
            ) in manager.bars_manager_integration.bars_manager.subscribed_tickers

        # Step 3: Check Redis for active quotes
        redis_client = await manager.get_redis()
        active_quotes = await redis_client.smembers('quotes:active')
        active_quotes = [
            q.decode('utf-8') if isinstance(q, bytes) else q for q in active_quotes]

        # Step 4: Check latest quote in Redis
        latest_quote_key = f'quote:latest:{symbol.upper()}'
        latest_quote = await redis_client.get(latest_quote_key)

        # Step 5: Check Redis subscription service health
        redis_service_health = None
        if manager.redis_subscription_service:
            redis_service_health = manager.redis_subscription_service.get_health_status()

        # Step 6: Try to get initial quote
        initial_quote = None
        if manager.bars_manager_integration:
            initial_quote = await manager.bars_manager_integration.get_initial_quote(symbol)

        return {
            'symbol': symbol.upper(),
            'test_results': {
                'websocket_subscribed': is_subscribed,
                'bars_manager_subscribed': bars_manager_subscribed,
                'redis_active_quotes': active_quotes,
                'redis_latest_quote_available': latest_quote is not None,
                'redis_latest_quote_data': latest_quote.decode('utf-8') if latest_quote else None,
                'initial_quote_available': initial_quote is not None,
                'initial_quote_data': initial_quote
            },
            'redis_service_health': redis_service_health,
            'diagnosis': {
                'issue': 'quote_flow_breakdown' if not is_subscribed or not bars_manager_subscribed else 'redis_subscription_issue' if not redis_service_health.get('running', False) else 'data_flow_issue',
                'recommendation': 'Check subscription flow' if not is_subscribed else 'Check BarsManager integration' if not bars_manager_subscribed else 'Check Redis subscription service' if not redis_service_health.get('running', False) else 'Check data flow from BarsManager to Redis'
            }
        }
    except Exception as e:
        return {'error': f'Failed to test quote flow: {str(e)}'}


@app.get('/debug_redis_subscriptions')
async def debug_redis_subscriptions() -> Dict[str, Any]:
    """Debug Redis subscription service status"""
    try:
        if not manager or not manager.redis_subscription_service:
            return {'error': 'Redis subscription service not available'}

        # Get detailed subscription status
        status = await manager.redis_subscription_service.debug_subscription_status()
        
        # Also check BarsManager integration status
        bars_manager_status = None
        if manager.bars_manager_integration:
            bars_manager_status = manager.bars_manager_integration.get_active_subscriptions()
        
        return {
            'status': 'success',
            'redis_subscription_service': status,
            'bars_manager_integration': bars_manager_status,
            'websocket_connections': len(manager.local_connections),
            'websocket_subscribed_symbols': list(manager.subscribed_symbols),
            'websocket_subscribed_bars': [f"{ticker}:{interval}" for ticker, interval in manager.subscribed_bars]
        }
    except Exception as e:
        return {'error': f'Failed to get debug status: {str(e)}'}


@app.post('/force_redis_resubscribe')
async def force_redis_resubscribe() -> Dict[str, Any]:
    """Force Redis subscription service to resubscribe to all channels"""
    try:
        if not manager or not manager.redis_subscription_service:
            return {'error': 'Redis subscription service not available'}

        # Force resubscribe
        await manager.redis_subscription_service.force_resubscribe()
        
        # Get updated status
        status = await manager.redis_subscription_service.debug_subscription_status()
        
        return {
            'status': 'success',
            'message': 'Redis subscriptions refreshed',
            'updated_status': status
        }
    except Exception as e:
        return {'error': f'Failed to force resubscribe: {str(e)}'}


@app.get('/api/mbs/{market_index}.json')
async def get_mbs(market_index: str = 'spx', start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]] | Dict[str, Any]:
    '''
    获取市场宽度分数
    :return:
    '''
    make_db_connection()
    return MarketBreadth.get_instance().get_market_breath(market_index=market_index, start_date=start_date,
                                                          end_date=end_date).dropna().drop(columns=['_id']).to_dict(orient='records')


@app.get('/api/market_pe/{index}.json')
async def get_market_pe(index: str = 'spx', start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
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
async def get_wedge_pop_tickers_of_today() -> Dict[str, Any] | List[Any]:
    wedge_pop: WedgePop = WedgePop.get_instance()
    return wedge_pop.get_wedge_tickers_on_today()


@app.get('/api/wedge_pop/wedges.json', description='Get wedge pop tickers since 1 year ago')
async def get_wedge_pop_tickers() -> Dict[str, Any] | List[Any]:
    wedge_pop: WedgePop = WedgePop.get_instance()
    start_date = datetime.now(tz=pytz.timezone(
        'America/New_York')) - timedelta(days=365)
    return wedge_pop.get_wedge_tickers_since(start_date)


@app.get('/api/wedge_pop/stats.json', description='Get wedge pop stats')
async def get_wedge_pop_stats(start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any] | List[Any]:
    wedge_pop: WedgePop = WedgePop.get_instance()
    return wedge_pop.get_wedge_stats(start_date=start_date, end_date=end_date)


@app.get('/api/ohlcvw/{ticker}.json', description='Get OHLCVW data for a ticker, default to 3 years ago')
async def get_ohlcvw(ticker: str, start_date: Optional[str] = None, end_date: Optional[str] = None, interval: str = '1d') -> Dict[str, Any] | List[Any]:
    md: MarketDataShovel = MarketDataShovel.get_instance()
    if start_date is None:
        start_date = (datetime.now(tz=pytz.timezone(
            'America/New_York')) - timedelta(days=365*3)).strftime('%Y-%m-%d')
    if end_date is None:
        end_date = (datetime.now(tz=pytz.timezone(
            'America/New_York'))).strftime('%Y-%m-%d')
    dailies_df = md.get_ticker_daily_info(
        ticker, start_date, end_date, interval=interval)
    dailies_df = dailies_df[['trade_date', 'ticker', 'open',
                             'high', 'low', 'close', 'volume', 'wedge_status']]
    return dailies_df.to_dict(orient='records')


# Watchlist endpoints
@app.get('/api/watchlist')
async def get_watchlist() -> Dict[str, Any]:
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
async def add_to_watchlist(ticker: str) -> Dict[str, Any]:
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
async def remove_from_watchlist(ticker: str) -> Dict[str, Any]:
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
