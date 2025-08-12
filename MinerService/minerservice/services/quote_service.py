"""Quote service for handling real-time quote data"""

import json
from datetime import datetime
from typing import Any, Dict, Optional

import yfinance as yf


class QuoteService:
    """Service for managing real-time quote data"""

    def __init__(self):
        self.cache_ttl = 60  # seconds

    def sanitize_symbol(self, symbol: str) -> str:
        """Clean symbol string for yfinance compatibility"""
        return ''.join(ch for ch in symbol if ch.isalnum() or ch in ['.', '='])

    def fetch_quote_from_yfinance(self, symbol: str) -> Dict[str, Any]:
        """Fetch real-time quote from yfinance"""
        try:
            clean_symbol = self.sanitize_symbol(symbol)
            ticker = yf.Ticker(clean_symbol)
            info = ticker.info

            return {
                'symbol': clean_symbol,
                'price': info.get('regularMarketPrice', 0),
                'change': info.get('regularMarketChange', 0),
                'changePercent': info.get('regularMarketChangePercent', 0),
                'volume': info.get('volume', 0),
                'marketCap': info.get('marketCap', 0),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            # Return fallback data on error
            return {
                'symbol': symbol,
                'price': 0,
                'change': 0,
                'changePercent': 0,
                'volume': 0,
                'marketCap': 0,
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }

    def is_price_changed(self, old_price: float, new_price: float, threshold: float = 0.001) -> bool:
        """Check if price has meaningfully changed"""
        return abs(new_price - old_price) > threshold

    def create_quote_cache_key(self, symbol: str) -> str:
        """Create Redis cache key for quote data"""
        return f"quote:{symbol}"

    def serialize_quote(self, quote_data: Dict[str, Any]) -> str:
        """Serialize quote data for caching"""
        return json.dumps(quote_data)

    def deserialize_quote(self, quote_json: str) -> Dict[str, Any]:
        """Deserialize cached quote data"""
        return json.loads(quote_json)
