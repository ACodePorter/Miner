"""Integration service for BarsManager to handle subscriptions and data flow"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from dataminer import BarsManager
from detonator import get_logger


class BarsManagerIntegration:
    """Service to integrate with BarsManager for real-time data management"""

    def __init__(self):
        self.logger = get_logger('BarsManagerIntegration', logging.DEBUG)
        self.bars_manager = BarsManager.get_instance()
        # Track active subscriptions
        self.active_quote_subscriptions: Set[str] = set()
        # (ticker, interval)
        self.active_bar_subscriptions: Set[Tuple[str, str]] = set()
        # Supported intervals from BarsManager
        self.supported_intervals = self.bars_manager.supported_intervals.copy()

    async def subscribe_to_quotes(self, ticker: str) -> bool:
        """Subscribe to quotes for a specific ticker via BarsManager"""
        if ticker not in self.active_quote_subscriptions:
            # Add to BarsManager subscription
            self.bars_manager.subscribe(ticker)
            self.active_quote_subscriptions.add(ticker)
            self.logger.info(
                f"Subscribed to quotes for {ticker} via BarsManager")
        else:
            self.logger.info(
                f"Already subscribed to quotes for {ticker} via BarsManager")
        return True

    async def unsubscribe_from_quotes(self, ticker: str) -> bool:
        """Unsubscribe from quotes for a specific ticker via BarsManager"""
        if ticker in self.active_quote_subscriptions:
            # Remove from BarsManager subscription
            self.bars_manager.unsubscribe(ticker)
            self.active_quote_subscriptions.remove(ticker)
            self.logger.info(
                f"Unsubscribed from quotes for {ticker} via BarsManager")
        else:
            self.logger.info(
                f"Already unsubscribed from quotes for {ticker} via BarsManager")
        return True

    async def subscribe_to_bars(self, ticker: str, interval: str) -> bool:
        """Subscribe to bars for a specific ticker and interval via BarsManager"""
        # Validate interval
        if interval not in self.supported_intervals:
            self.logger.warning(
                f"Unsupported interval {interval} for {ticker}")
            return False

        subscription_key = (ticker, interval)
        if subscription_key not in self.active_bar_subscriptions:
            # Add to BarsManager intraday subscription
            self.bars_manager.subscribe_intraday(ticker, interval)
            self.active_bar_subscriptions.add(subscription_key)
            self.logger.info(
                f"Subscribed to {interval} bars for {ticker} via BarsManager")
        else:
            self.logger.info(
                f"Already subscribed to {interval} bars for {ticker} via BarsManager")
        return True

    async def unsubscribe_from_bars(self, ticker: Optional[str], interval:Optional[str]) -> bool:
        """Unsubscribe from bars for a specific ticker and interval via BarsManager"""
        subscription_key = (ticker, interval)
        if subscription_key in self.active_bar_subscriptions:
            # Remove from BarsManager intraday subscription
            self.bars_manager.unsubscribe_intraday(ticker, interval)
            self.active_bar_subscriptions.remove(subscription_key)
            self.logger.info(
                f"Unsubscribed from {interval} bars for {ticker} via BarsManager")
        else:
            self.logger.info(
                f"Already unsubscribed from {interval} bars for {ticker} via BarsManager")
        return True

    async def get_initial_bars_snapshot(self, ticker: str, interval: str) -> Optional[List[Dict[str, Any]]]:
        """Get initial bars snapshot for a ticker and interval"""
        # Get maximum available bars from BarsManager for initial chart loading
        # Use 'max' period to get all available historical data
        bars_df = self.bars_manager.get_bars(ticker, interval, 'max')

        if bars_df.empty:
            self.logger.warning(
                f"No bars data available for {ticker} {interval}")
            return None

        # Convert to list of dictionaries
        bars = []
        for index, row in bars_df.iterrows():
            bars.append({
                # Convert to milliseconds
                'timestamp': int(index.timestamp() * 1000),
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': int(row['Volume'])
            })

        self.logger.info(
            f"Retrieved {len(bars)} initial bars for {ticker} {interval}")
        return bars

    async def get_initial_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get initial quote data for a ticker"""
        # First try to get recent quote from BarsManager (Redis)
        quote_data = self.bars_manager.get_latest_quote(ticker)
        # Check if quote_data is empty dict or None
        if not quote_data:
            self.logger.warning(
                f"No stored quote data available for {ticker}, checking if subscribed")
            # Check if ticker is subscribed to live quotes
            if ticker.upper() in self.bars_manager.subscribed_tickers:
                self.logger.info(
                    f"{ticker} is subscribed to live quotes, will receive updates soon")
                # Return a placeholder that indicates subscription is active
                return {
                    'symbol': ticker,
                    'price': 0,  # Will be updated via real-time stream
                    'change': 0,
                    'changePercent': 0,
                    'volume': 0,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'subscribed_waiting_for_data'
                }
            else:
                self.logger.warning(
                    f"{ticker} is not subscribed to live quotes")
                return None
        # Convert to standardized format
        quote = {
            'symbol': ticker,
            'price': float(quote_data.get('price', 0)),
            'change': float(quote_data.get('change', 0)),
            'changePercent': float(quote_data.get('change_percent', 0)),
            'volume': int(quote_data.get('day_volume', 0)),
            'timestamp': quote_data.get('timestamp', datetime.now().isoformat())
        }
        return quote


    def is_quote_subscribed(self, ticker: str) -> bool:
        return ticker in self.bars_manager.get_subscribed_quotes_tickers()

    def is_bar_subscribed(self, ticker: str, interval:str) -> bool:
        bars = self.bars_manager.get_subscribed_intraday()
        return interval in bars and ticker in bars[interval]

    def get_active_subscriptions(self) -> Dict[str, Any]:
        """Get current active subscriptions"""
        return {
            'quotes': list(self.active_quote_subscriptions),
            'bars': [f"{ticker}:{interval}" for ticker, interval in self.active_bar_subscriptions]
        }

    def get_supported_intervals(self) -> List[str]:
        """Get list of supported intervals"""
        return self.supported_intervals.copy()

    async def cleanup(self) -> None:
        """Cleanup all subscriptions when service is stopped"""
        try:
            # Unsubscribe from all quotes
            for ticker in list(self.active_quote_subscriptions):
                await self.unsubscribe_from_quotes(ticker)
            # Unsubscribe from all bars
            for ticker, interval in list(self.active_bar_subscriptions):
                await self.unsubscribe_from_bars(ticker, interval)
            self.logger.info("Cleaned up all BarsManager subscriptions")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    def is_subscribed_to_quotes(self, ticker: str) -> bool:
        """Check if subscribed to quotes for a ticker"""
        return ticker in self.active_quote_subscriptions

    def is_subscribed_to_bars(self, ticker: str, interval: str) -> bool:
        """Check if subscribed to bars for a ticker and interval"""
        return (ticker, interval) in self.active_bar_subscriptions


    def dump(self):
        return {
            'active_quote_subscriptions':self.active_quote_subscriptions,
            'active_bar_subscriptions':self.active_bar_subscriptions,
        }