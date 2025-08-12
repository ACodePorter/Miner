"""Bars service for handling real-time bars data"""

import hashlib
import json
import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from dataminer import BarsManager


class BarsService:
    """Service for managing real-time bars data"""

    def __init__(self):
        self.bars_manager = BarsManager.get_instance()
        self.cache_ttl = 300  # 5 minutes for bars data

    def _safe_float(self, value: Any) -> float:
        """Safely convert value to float, handling nan and inf values"""
        try:
            if value is None or (isinstance(value, float) and math.isnan(value)):
                return 0.0
            if isinstance(value, float) and math.isinf(value):
                return 0.0
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def _safe_int(self, value: Any) -> int:
        """Safely convert value to int, handling nan and inf values"""
        try:
            if value is None or (isinstance(value, float) and math.isnan(value)):
                return 0
            if isinstance(value, float) and math.isinf(value):
                return 0
            return int(float(value))
        except (ValueError, TypeError):
            return 0

    def get_initial_bars_snapshot(self, symbol: str, interval: str) -> List[Dict[str, Any]]:
        """Get initial bars snapshot for chart loading"""
        try:
            hist = self.bars_manager.get_bars(symbol, interval, 'max')
            if hist.empty:
                return []

            bars = []
            for index, row in hist.iterrows():
                # Safely convert values, handling nan and inf
                open_price = self._safe_float(row['Open'])
                high_price = self._safe_float(row['High'])
                low_price = self._safe_float(row['Low'])
                close_price = self._safe_float(row['Close'])
                volume = self._safe_int(row['Volume'])

                # Skip bars with invalid data (all zeros might indicate bad data)
                if all(price == 0.0 for price in [open_price, high_price, low_price, close_price]):
                    continue

                bars.append({
                    'timestamp': int(index.timestamp() * 1000),
                    'open': open_price,
                    'high': high_price,
                    'low': low_price,
                    'close': close_price,
                    'volume': volume
                })

            return bars
        except Exception as e:
            print(f"Error getting initial bars for {symbol} {interval}: {e}")
            return []

    def get_recent_bars_for_comparison(self, symbol: str, interval: str, count: int = 10) -> Optional[Any]:
        """Get recent bars for incremental update comparison"""
        try:
            return self.bars_manager.get_recent_bars(symbol, interval, count)
        except Exception as e:
            print(f"Error getting recent bars for {symbol} {interval}: {e}")
            return None

    def create_bars_data_hash(self, bar_data: Dict[str, Any]) -> str:
        """Create hash for bars data to detect changes"""
        data_string = f"{bar_data['open']}{bar_data['high']}{bar_data['low']}{bar_data['close']}{bar_data['volume']}"
        return hashlib.md5(data_string.encode()).hexdigest()

    def is_bar_too_old(self, bar_timestamp: datetime, interval: str) -> bool:
        """Check if bar is too old to be relevant"""
        current_time = datetime.now()
        time_diff = current_time - bar_timestamp

        # Skip if bar is older than 1 hour for minute intervals, 1 day for others
        max_age_hours = 1 if interval in [
            '1m', '5m', '15m', '30m', '60m', '65m'] else 24
        return time_diff.total_seconds() > max_age_hours * 3600

    def create_bars_cache_key(self, symbol: str, interval: str, timestamp: int) -> str:
        """Create Redis cache key for bars data"""
        return f"bars:{symbol}:{interval}:{timestamp}"

    def create_bars_hash_cache_key(self, symbol: str, interval: str, timestamp: int) -> str:
        """Create Redis cache key for bars hash"""
        return f"bars:{symbol}:{interval}:{timestamp}:hash"

    def create_last_check_hash_key(self, symbol: str, interval: str) -> str:
        """Create Redis cache key for last check hash"""
        return f"bars:{symbol}:{interval}:last_check_hash"

    def serialize_bars_data(self, bars_data: Dict[str, Any]) -> str:
        """Serialize bars data for caching"""
        return json.dumps(bars_data)

    def deserialize_bars_data(self, bars_json: str) -> Dict[str, Any]:
        """Deserialize cached bars data"""
        return json.loads(bars_json)

    def format_bars_message(self, symbol: str, interval: str, bars: List[Dict[str, Any]], is_snapshot: bool = False) -> Dict[str, Any]:
        """Format bars data for WebSocket transmission"""
        return {
            'type': 'bars',
            'data': {
                'symbol': symbol,
                'interval': interval,
                'bars': bars,
                'is_snapshot': is_snapshot
            },
            'timestamp': datetime.now().isoformat()
        }
