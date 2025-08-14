"""Configuration for BarsManager integration"""

from typing import List

# Supported intervals from BarsManager
SUPPORTED_INTERVALS: List[str] = ['1m', '5m', '15m', '30m', '65m']

# Redis channel patterns
QUOTES_CHANNEL_PATTERN: str = "quotes:{ticker}"
BARS_CHANNEL_PATTERN: str = "bars:{ticker}:{interval}"

# WebSocket message types
MESSAGE_TYPE_QUOTE: str = 'quote'
MESSAGE_TYPE_BARS: str = 'bars'

# Data field mappings from BarsManager to WebSocket
QUOTE_FIELD_MAPPING = {
    'price': 'price',
    'change': 'change',
    'change_percent': 'changePercent',
    'volume': 'volume',
    'timestamp': 'timestamp'
}

BARS_FIELD_MAPPING = {
    'timestamp': 'timestamp',
    'open': 'open',
    'high': 'high',
    'low': 'low',
    'close': 'close',
    'volume': 'volume'
}

# Health check settings
BARS_MANAGER_HEALTH_CHECK_INTERVAL: int = 60  # seconds
REDIS_HEALTH_CHECK_INTERVAL: int = 30  # seconds

# Error handling
MAX_RETRY_ATTEMPTS: int = 3
RETRY_DELAY: int = 5  # seconds

# Performance settings
MAX_CONCURRENT_SUBSCRIPTIONS: int = 1000
SUBSCRIPTION_BATCH_SIZE: int = 50
