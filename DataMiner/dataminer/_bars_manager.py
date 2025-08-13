import json
import logging
from datetime import datetime
from typing import Any, Dict, Literal, Union

import pandas as pd
import yfinance as yf
from detonator import SingletonParent, get_logger, get_redis_client
from pandas import DataFrame

from ._live_quote_source import LiveQuoteSource


class BarsManager(SingletonParent):
    """
    BarsManager for fetching and managing bar data from yfinance.

    Usage Rules:
    1. get_bars(): Use for fetching full historical data (e.g., initial chart load)
    2. get_recent_bars(): Use for incremental updates and real-time comparison

    Redis Quote Publishing:
    Live quotes are published to Redis for real-time consumption by other services.

    Redis Key Structure:
    - Channel: "quotes:{ticker}" - Redis pub/sub channel for each ticker
    - Channel: "quote:latest" - Redis pub/sub channel for latest quote for all tickers
    - Key: "quote:latest:{ticker}" - Latest quote data for each ticker
    - Key: "quotes:active" - Set of currently active tickers with live quotes

    Example Redis subscription:
        redis_client.subscribe("quotes:AAPL")  # Subscribe to AAPL quotes
        redis_client.subscribe("quotes:*")     # Subscribe to all quote channels

    Quote Data Format:
        The quote dict is published as-is via Redis pub/sub and also stored as JSON
        in the latest quote key for historical reference.
    """

    def __init__(self):
        self.bars = {}
        self.logger = get_logger('BarsManager', logging.NOTSET)
        self.subscribed_tickers = set()
        self.ws = None
        self.redis_client = get_redis_client()

    def resample_session(self, g: DataFrame) -> DataFrame:
        # Anchor bins at 09:30 for this day
        agg = {
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
        }

        day_midnight = g.index[0].normalize()
        session_start = day_midnight + pd.Timedelta(hours=9, minutes=30)
        return g.resample(
            "65min",
            origin=session_start,
            closed="left",
            label="left",
        ).agg(agg)

    def get_bars(self, ticker: str,
                 interval: Literal['1m', '2m', '5m', '15m', '30m', '65m',
                                   '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo'] = '1d',
                 period: Literal['1d', '5d', '1mo', '3mo', '6mo',
                                 '1y', '2y', '5y', '10y', 'ytd', 'max'] = '1y',
                 start_date: Literal[str, datetime, None] = None) -> DataFrame:
        """ get bars from yfinance

        Args:
            ticker (str): ticker symbol
            interval (Literal['1m', '2m', '5m', '15m', '30m', '65m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo'], optional): interval. Defaults to '1d'.
            period (Literal['1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max'], optional): period. Defaults to '1y'.
            start_date (Literal[str, datetime, None], optional): start date. Defaults to None, if str, it should be in format YYYYMMDD or YYYY-MM-DD.

        Returns:
            DataFrame: bars DataFrame
        """
        # 1-min data; regular trading hours
        resample_bars = interval == '65m'
        interval = '5m' if resample_bars else interval
        period = 'max' if resample_bars else period
        # if start_date is str and in format YYYYMMDD, convert it to YYYY-MM-DD
        if isinstance(start_date, str) and len(start_date) == 8:
            start_date = datetime.strptime(start_date, '%Y%m%d')
        start_date = start_date.strftime(
            '%Y-%m-%d') if isinstance(start_date, datetime) else start_date

        bars = yf.Ticker(ticker).history(
            period=period, interval=interval, start=start_date, actions=False, prepost=False, rounding=True)

        if resample_bars:
            bars = (
                bars
                .groupby(bars.index.normalize())
                .apply(self.resample_session)
                .droplevel(0)
                .dropna(how="all")
            )

        return bars

    def get_recent_bars(self, ticker: str, interval: str, count: int = 10) -> DataFrame:
        """Get the most recent bars for incremental updates and comparison

        Args:
            ticker (str): ticker symbol
            interval (str): interval string
            count (int): number of recent bars to return

        Returns:
            DataFrame: recent bars DataFrame optimized for incremental updates
        """
        # For minute intervals, get enough data to ensure we have current session
        if interval in ['1m', '2m', '5m', '15m', '30m', '65m', '90m', '1h']:
            period = '1d'  # Get 1 day for current session data
        else:
            period = '3d'  # Get 3 days for daily/weekly data

        bars = self.get_bars(ticker, interval, period)
        if bars.empty:
            return bars

        # Return the last N bars for incremental comparison
        return bars.tail(count)

    def handle_quote(self, quote: Dict[str, Any]):
        """Handle incoming quote and publish to Redis for real-time distribution"""
        self.logger.info(
            f'{datetime.fromtimestamp(int(quote["time"])/1000).strftime("%H:%M:%S")} {quote["id"]}: {quote["price"]} {quote["change"]} {quote["change_percent"]}')
        # Extract ticker from quote (quote has 'id' field)
        ticker = quote.get('id')
        if not ticker:
            self.logger.warning(
                "Could not extract ticker from quote: %s", quote)
            return
        try:
            # Publish quote to Redis pub/sub channel
            channel = f'quotes:{ticker}'
            self.redis_client.publish(channel, json.dumps(quote))
            self.redis_client.publish('quote:latest', json.dumps(quote))
            # Store latest quote for historical reference
            latest_key = f'quote:latest:{ticker}'
            self.redis_client.setex(
                latest_key, 300, json.dumps(quote))  # Expire in 1 hour
            # Add ticker to active quotes set
            self.redis_client.sadd('quotes:active', ticker)
            self.logger.debug('Published quote for %s to Redis', ticker)
        except Exception as e:
            self.logger.error('Failed to publish quote to Redis: %s', e)

    def subscribe(self, ticker: Union[str, list[str]]):
        if isinstance(ticker, str):
            ticker = [ticker]
        ticker = [t.upper().replace('.', '-') for t in ticker]
        self.subscribed_tickers.update(ticker)
        if self.ws is None:
            self._start_live_quotes()
        else:
            try:
                self.ws.subscribe(tickers=ticker)
            except Exception as e:
                self.logger.error(f"Error subscribing to {ticker}: {e}")
                self.subscribed_tickers.difference_update(ticker)

    def unsubscribe(self, ticker: Union[str, list[str]]):
        if isinstance(ticker, str):
            ticker = [ticker]
        ticker = [t.upper().replace('.', '-') for t in ticker]
        self.subscribed_tickers.difference_update(ticker)

        # Remove from Redis active set
        for t in ticker:
            self.redis_client.srem("quotes:active", t)

        if self.ws is not None:
            try:
                self.ws.unsubscribe(ticker)
            except Exception as e:
                self.logger.error(f"Error unsubscribing from {ticker}: {e}")
                self.subscribed_tickers.update(ticker)
                # Re-add to Redis active set if subscription failed
                for t in ticker:
                    self.redis_client.sadd("quotes:active", t)

    def _on_error(self, e: Exception):
        self.logger.error(f"Error in WebSocket: {str(e)}, lets restart it")
        self.restart_live_quotes()

    def _start_live_quotes(self):
        if self.ws is None:
            self.ws = LiveQuoteSource(self.handle_quote, self._on_error)
            self.ws.subscribe(list(self.subscribed_tickers))
        else:
            self.logger.info("Live quotes already started")

    def _init_redis_keys(self):
        """Initialize Redis keys and sets for quote management"""
        try:
            # Clear any stale active tickers set
            self.redis_client.delete("quotes:active")
            # Add current subscribed tickers to active set
            if self.subscribed_tickers:
                for ticker in self.subscribed_tickers:
                    self.redis_client.sadd("quotes:active", ticker)
                self.logger.info("Initialized Redis keys for %d tickers", len(
                    self.subscribed_tickers))
        except Exception as e:
            self.logger.error("Failed to initialize Redis keys: %s", e)

    def restart_live_quotes(self):
        self.stop_live_quotes()
        self._start_live_quotes()

    def get_active_tickers(self) -> set[str]:
        """Get the set of currently active tickers with live quotes from Redis"""
        try:
            active_tickers = self.redis_client.smembers("quotes:active")
            return {ticker.decode('utf-8') if isinstance(ticker, bytes) else ticker
                    for ticker in active_tickers}
        except Exception as e:
            self.logger.error("Failed to get active tickers from Redis: %s", e)
            return set()

    def get_latest_quote(self, ticker: str) -> Dict[str, Any]:
        """Get the latest quote for a specific ticker from Redis"""
        try:
            latest_key = f"quote:latest:{ticker}"
            quote_data = self.redis_client.get(latest_key)
            if quote_data:
                if isinstance(quote_data, bytes):
                    quote_data = quote_data.decode('utf-8')
                return json.loads(quote_data)
            return {}
        except Exception as e:
            self.logger.error(
                "Failed to get latest quote for %s from Redis: %s", ticker, e)
            return {}

    def stop_live_quotes(self):
        if self.ws is not None:
            self.ws.stop()
            self.ws = None
            # Clear all active tickers from Redis when stopping
            try:
                self.redis_client.delete("quotes:active")
                self.logger.info("Cleared active tickers from Redis")
            except Exception as e:
                self.logger.error(
                    "Failed to clear active tickers from Redis: %s", e)
        else:
            self.logger.info("Live quotes already stopped")
