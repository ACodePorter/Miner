import json
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Union

import pandas as pd
import pytz
import yfinance as yf
from detonator import SingletonParent, get_logger, get_redis_client
from pandas import DataFrame

from ._live_quote_source import LiveQuoteSource
from ._trade_cal import TradeCalendarShovel


class BarsManager(SingletonParent):
    """
    BarsManager for fetching and managing bar bars from yfinance.

    Usage Rules:
    1. get_bars(): Use for fetching full historical bars (e.g., initial chart load)
    2. get_recent_bars(): Use for incremental updates and real-time comparison
    3. subscribe_intraday(): Use for real-time intraday bar updates

    Redis Quote Publishing:
    Live quotes are published to Redis for real-time consumption by other services.

    Redis Key Structure:
    - Channel: "quotes:{ticker}" - Redis pub/sub channel for each ticker
    - Channel: "quote:latest" - Redis pub/sub channel for latest quote for all tickers
    - Key: "quote:latest:{ticker}" - Latest quote bars for each ticker
    - Key: "quotes:active" - Set of currently active tickers with live quotes

    Redis Bar Publishing:
    Intraday bars are published to Redis for real-time consumption.

    Redis Bar Key Structure:
    - Channel: "bars:{ticker}:{interval}" - Redis pub/sub channel for each ticker/interval
    - Channel: "bars:latest:{interval}" - Redis pub/sub channel for latest bars for all tickers
    - Key: "bars:latest:{ticker}:{interval}" - Latest bar bars for each ticker/interval
    - Key: "bars:active:{interval}" - Set of currently active tickers with bars for each interval

    Example Redis subscription:
        redis_client.subscribe("quotes:AAPL")  # Subscribe to AAPL quotes
        redis_client.subscribe("bars:AAPL:5m")  # Subscribe to AAPL 5-minute bars
        redis_client.subscribe("bars:*:1m")     # Subscribe to all 1-minute bars
    """

    KEY_QUOTES_ACTIVE = 'quotes:active'
    KEY_QUOTES_SUBSCRIBED = 'quotes:subscribed'
    KEY_BARS_ACTIVE = 'bars:active'
    KEY_BARS_SUBSCRIBED = 'bars:subscribed'

    def __init__(self):
        self.bars = {}
        self.logger = get_logger('BarsManager', logging.DEBUG)
        self.subscribed_tickers = set()
        self.ws = None
        self.redis_client = get_redis_client()
        self.redis_client.delete(BarsManager.KEY_QUOTES_ACTIVE)
        self.redis_client.delete(BarsManager.KEY_QUOTES_SUBSCRIBED)
        self.redis_client.delete(BarsManager.KEY_BARS_ACTIVE)
        self.redis_client.delete(BarsManager.KEY_BARS_SUBSCRIBED)

        # Intraday bars subscription management
        self.intraday_subscriptions = {}  # {interval: set(tickers)}
        self.scheduling_thread = None
        self.scheduling_active = False

        # Initialize supported intervals
        self.supported_intervals = ['1m', '5m', '15m', '30m', '65m']

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
                 start_date: Union[str, datetime, None] = None) -> DataFrame:
        """ get bars from yfinance

        Args:
            ticker (str): ticker symbol
            interval (Literal['1m', '2m', '5m', '15m', '30m', '65m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo'], optional): interval. Defaults to '1d'.
            period (Literal['1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max'], optional): period. Defaults to '1y'.
            start_date (Union[str, datetime, None], optional): start date. Defaults to None, if str, it should be in format YYYYMMDD or YYYY-MM-DD.

        Returns:
            DataFrame: bars DataFrame
        """
        # 1-min bars; regular trading hours
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
        # For minute intervals, get enough bars to ensure we have current session
        if interval in ['1m', '2m', '5m', '15m', '30m', '65m', '90m', '1h']:
            period = '1d'  # Get 1 day for current session bars
        else:
            period = '3d'  # Get 3 days for daily/weekly bars

        bars = self.get_bars(ticker, interval, period)
        if bars.empty:
            return bars

        # Return the last N bars for incremental comparison
        return bars.tail(count)

    def handle_quote(self, quote: Dict[str, Any]):
        """Handle incoming quote and publish to Redis for real-time distribution"""
        ticker = quote.get('id')
        if not ticker:
            self.logger.warning(
                "Could not extract ticker from quote: %s", quote)
            return
        try:
            # Publish quote to Redis pub/sub channel
            channel = f'quotes:{ticker}'
            quote_json = json.dumps(quote)
            self.redis_client.publish(channel, quote_json)
            self.redis_client.publish('quote:latest', quote_json)
            # Store latest quote for historical reference
            latest_key = f'quote:latest:{ticker}'
            self.redis_client.setex(
                latest_key, 10, quote_json)  # Expire in 1 hour
            # Add ticker to active quotes set
            self.redis_client.sadd('quotes:active', ticker)
            self.logger.debug('Published quote to %s -> %s',
                              channel, quote_json)
        except Exception as e:
            self.logger.error('Failed to publish quote to Redis: %s', e)

    def _sync_subscribed_quotes_to_redis(self):
        try:
            with self.redis_client.pipeline() as pipe:
                pipe.delete(BarsManager.KEY_QUOTES_ACTIVE)
                for t in self.subscribed_tickers:
                    pipe.sadd(BarsManager.KEY_QUOTES_SUBSCRIBED, t)
                pipe.execute()
        except Exception as e:
            self.logger.error(
                'Failed to update subscribes tickers to Redis: %s', e)

    def subscribe(self, ticker: Union[str, List[str]]):
        if isinstance(ticker, str):
            ticker = [ticker]
        ticker = [t.upper().replace('.', '-') for t in ticker]
        self.subscribed_tickers.update(ticker)
        self._sync_subscribed_quotes_to_redis()
        if self.ws is None:
            self._start_live_quotes()
        else:
            try:
                self.ws.subscribe(tickers=ticker)
            except Exception as e:
                self.logger.error(f"Error subscribing to {ticker}: {e}")
                self.subscribed_tickers.difference_update(ticker)

    def unsubscribe(self, ticker: Union[str, List[str]]):
        if isinstance(ticker, str):
            ticker = [ticker]
        ticker = [t.upper().replace('.', '-') for t in ticker]
        self.subscribed_tickers.difference_update(ticker)
        self._sync_subscribed_quotes_to_redis()
        # Remove from Redis active set
        for t in ticker:
            self.redis_client.srem("quotes:active", t)

        if self.ws is not None:
            try:
                self.ws.unsubscribe(ticker)
                if not self.subscribed_tickers:
                    self.stop_live_quotes()
            except Exception as e:
                self.logger.error(f"Error unsubscribing from {ticker}: {e}")
                self.subscribed_tickers.update(ticker)
                # Re-add to Redis active set if subscription failed
                for t in ticker:
                    self.redis_client.sadd("quotes:active", t)

    def get_subscribed_quotes_tickers(self) -> List[str]:
        '''
        Get list of subscribed tickers of all processes
        '''
        try:
            return list(self.redis_client.smembers(BarsManager.KEY_QUOTES_ACTIVE))
        except Exception as _:
            return list(self.subscribed_tickers)

    def _sync_subscribed_bars_to_redis(self):
        try:
            bars = {k: list(v) for k, v in self.intraday_subscriptions.items()}
            with self.redis_client.pipeline() as pipe:
                pipe.delete(BarsManager.KEY_BARS_SUBSCRIBED)
                pipe.hset(BarsManager.KEY_BARS_SUBSCRIBED, mapping=bars)
                pipe.execute()
        except Exception as e:
            self.logger.error(
                'Failed to update subscribed bars to Redis: %s', e)

    def subscribe_intraday(self, tickers: Union[str, List[str]], intervals: Union[str, List[str]]):
        """Subscribe to intraday bars for specified tickers and intervals

        Args:
            tickers: Single ticker or list of tickers
            intervals: Single interval or list of intervals from ['1m', '5m', '15m', '30m', '65m']
        """
        if isinstance(tickers, str):
            tickers = [tickers]
        if isinstance(intervals, str):
            intervals = [intervals]

        # Normalize tickers and validate intervals
        tickers = [t.upper().replace('.', '-') for t in tickers]
        intervals = [i for i in intervals if i in self.supported_intervals]

        if not intervals:
            self.logger.warning("No valid intervals provided")
            return

        # Update subscriptions
        for interval in intervals:
            if interval not in self.intraday_subscriptions:
                self.intraday_subscriptions[interval] = set()
            self.intraday_subscriptions[interval].update(tickers)
        self._sync_subscribed_bars_to_redis()
        # Start scheduling if not already active
        if not self.scheduling_active:
            self._start_intraday_scheduling()

        # Initialize Redis keys for new subscriptions
        self._init_redis_bar_keys()

        self.logger.info(
            f"Subscribed to intraday bars: {tickers} for intervals: {intervals}")

    def unsubscribe_intraday(self, tickers: Union[str, List[str]], intervals: Union[str, List[str]]):
        """Unsubscribe from intraday bars for specified tickers and intervals

        Args:
            tickers: Single ticker or list of tickers
            intervals: Single interval or list of intervals from ['1m', '5m', '15m', '30m', '65m']
        """
        if isinstance(tickers, str):
            tickers = [tickers]
        if isinstance(intervals, str):
            intervals = [intervals]

        tickers = [t.upper().replace('.', '-') for t in tickers]

        # Update subscriptions
        for interval in intervals:
            if interval in self.intraday_subscriptions:
                self.intraday_subscriptions[interval].difference_update(
                    tickers)

                # Remove from Redis active set
                for ticker in tickers:
                    self.redis_client.srem(f"bars:active:{interval}", ticker)
                    # Remove latest bar bars
                    self.redis_client.delete(
                        f"bars:latest:{ticker}:{interval}")

                # Clean up empty interval subscriptions
                if not self.intraday_subscriptions[interval]:
                    del self.intraday_subscriptions[interval]
        self._sync_subscribed_bars_to_redis()
        # Stop scheduling if no more subscriptions
        if (not self.intraday_subscriptions) and self.scheduling_active:
            self._stop_intraday_scheduling()

        self.logger.info(
            f"Unsubscribed from intraday bars: {tickers} for intervals: {intervals}")

    def get_subscribed_intraday(self) -> Dict[str, List[str]]:
        try:
            return self.redis_client.hgetall(BarsManager.KEY_BARS_SUBSCRIBED)
        except Exception as e:
            return {K: list(V) for K, V in self.intraday_subscriptions.items()}

    def _on_error(self, e: Exception):
        self.logger.error(f"Error in WebSocket: {str(e)}, lets restart it")
        self.restart_live_quotes()

    def _start_live_quotes(self):
        if self.ws is None:
            self.logger.info("Starting live quotes")
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

    def _init_redis_bar_keys(self):
        """Initialize Redis keys and sets for bar management"""
        try:
            for interval, tickers in self.intraday_subscriptions.items():
                active_key = f"bars:active:{interval}"
                # Clear any stale active tickers set
                self.redis_client.delete(active_key)
                # Add current subscribed tickers to active set
                if tickers:
                    for ticker in tickers:
                        self.redis_client.sadd(active_key, ticker)
            self.logger.info("Initialized Redis bar keys for intervals: %s", list(
                self.intraday_subscriptions.keys()))
        except Exception as e:
            self.logger.error("Failed to initialize Redis bar keys: %s", e)

    def _start_intraday_scheduling(self):
        """Start the background thread for intraday bar scheduling"""
        if self.scheduling_thread is None or not self.scheduling_thread.is_alive():
            self.scheduling_active = True
            self.scheduling_thread = threading.Thread(
                target=self._schedule_bar_updates, daemon=True)
            self.scheduling_thread.start()
            self.logger.info("Started intraday bar scheduling thread")

    def _stop_intraday_scheduling(self):
        """Stop the background thread for intraday bar scheduling"""
        self.scheduling_active = False
        if self.scheduling_thread and self.scheduling_thread.is_alive():
            self.scheduling_thread.join(timeout=5)
            self.scheduling_thread = None
            self.logger.info("Stopped intraday bar scheduling thread")

    def _schedule_bar_updates(self):
        """Main scheduling loop for intraday bar updates with precise timing"""
        self.logger.info("Intraday bar scheduling started")

        while self.scheduling_active:
            try:
                now = datetime.now(pytz.timezone('America/New_York'))

                # Log current time for debugging
                self.logger.debug(
                    f"Current time: {now.strftime('%H:%M:%S')} (weekday: {now.weekday()})")

                # Check which intervals need updates
                intervals_to_update = []
                for interval in list(self.intraday_subscriptions.keys()):
                    is_update_time = self._is_time_for_update(now, interval)
                    self.logger.debug(
                        f"Interval {interval}: is_update_time={is_update_time}")
                    if is_update_time:
                        intervals_to_update.append(interval)

                if intervals_to_update:
                    self.logger.info(
                        f"Updating bars for intervals: {intervals_to_update}")
                    for interval in intervals_to_update:
                        self._update_bars_for_interval(interval)
                else:
                    self.logger.debug("No intervals to update at this time")

                # Calculate optimal sleep time to align with next update opportunity
                sleep_seconds = self._calculate_optimal_sleep_time(now)

                # Log timing information for debugging
                if sleep_seconds > 10:  # Only log longer sleeps to avoid spam
                    self.logger.debug(
                        f"Sleeping for {sleep_seconds:.2f}s until next update opportunity")
                else:
                    self.logger.debug(f"Sleeping for {sleep_seconds:.2f}s")

                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)
                else:
                    # If we're already past the boundary, sleep for a short time
                    time.sleep(1)

            except Exception as e:
                self.logger.error(f"Error in bar scheduling loop: {e}")
                time.sleep(30)  # Wait longer on error

        self.logger.info("Intraday bar scheduling stopped")

    def _is_time_for_update(self, current_time: datetime, interval: str) -> bool:
        """Check if it's time to update bars for the given interval"""
        tc = TradeCalendarShovel.get_instance()
        market_open = tc.is_mkt_open()
        self.logger.debug(f"Market open check result: {market_open}")

        if not market_open:
            # Fallback: check if we're in normal market hours (9:30 AM - 4:00 PM ET, Mon-Fri)
            # This handles cases where the database might not have current trading day bars
            if self._is_in_normal_market_hours(current_time):
                self.logger.debug(
                    f"Market closed in DB but in normal hours, allowing updates for {interval}")
                market_open = True
            else:
                self.logger.debug(
                    f"Market is closed, no updates for {interval}")
                return False

        # Allow updates within a 5-second window around the boundary
        # This makes the system more robust to slight timing variations
        tolerance_seconds = 10

        if interval == '1m':
            # For 1m, allow updates within 5 seconds of :00
            is_update_time = current_time.second < tolerance_seconds
            self.logger.debug(
                f"1m interval: current_second={current_time.second}, tolerance={tolerance_seconds}, is_update_time={is_update_time}")
            return is_update_time
        elif interval == '5m':
            # For 5m, allow updates within 5 seconds of :00, :05, :10, etc.
            minute_check = current_time.minute % 5 == 0
            second_check = current_time.second < tolerance_seconds
            is_update_time = minute_check and second_check
            self.logger.debug(
                f"5m interval: current_minute={current_time.minute}, minute_check={minute_check}, current_second={current_time.second}, second_check={second_check}, is_update_time={is_update_time}")
            return is_update_time
        elif interval == '15m':
            # For 15m, allow updates within 5 seconds of :00, :15, :30, :45
            minute_check = current_time.minute % 15 == 0
            second_check = current_time.second < tolerance_seconds
            is_update_time = minute_check and second_check
            self.logger.debug(
                f"15m interval: current_minute={current_time.minute}, minute_check={minute_check}, current_second={current_time.second}, second_check={second_check}, is_update_time={is_update_time}")
            return is_update_time
        elif interval == '30m':
            # For 30m, allow updates within 5 seconds of :00, :30
            minute_check = current_time.minute % 30 == 0
            second_check = current_time.second < tolerance_seconds
            is_update_time = minute_check and second_check
            self.logger.debug(
                f"30m interval: current_minute={current_time.minute}, minute_check={minute_check}, current_second={current_time.second}, second_check={second_check}, is_update_time={is_update_time}")
            return is_update_time
        elif interval == '65m':
            is_update_time = self._is_65m_update_time(current_time)
            self.logger.debug(f"65m interval: is_update_time={is_update_time}")
            return is_update_time
        return False

    def _is_65m_update_time(self, current_time: datetime) -> bool:
        """Check if it's time for 65m bar update (market session based)"""
        # Market hours: 9:30 AM to 4:00 PM
        market_open = current_time.replace(
            hour=9, minute=30, second=0, microsecond=0)
        market_close = current_time.replace(
            hour=16, minute=1, second=0, microsecond=0)
        if current_time < market_open or current_time > market_close:
            return False
        # Check if current time aligns with 65-minute boundaries
        elapsed_from_open = current_time - market_open
        elapsed_minutes = int(elapsed_from_open.total_seconds() / 60)
        # 65-minute boundaries: 0, 65, 130, 195, 260, 325 minutes from market open
        if elapsed_minutes % 65 == 0:
            return True
        return False

    def _is_trading_day(self, dt: datetime) -> bool:
        """Check if date is a trading day (Monday-Friday)"""
        return dt.weekday() < 5  # Monday=0, Friday=4

    def _is_in_normal_market_hours(self, current_time: datetime) -> bool:
        """Fallback check for normal market hours (9:30 AM - 4:00 PM ET, Mon-Fri)"""
        # Check if it's a weekday
        if current_time.weekday() >= 5:  # Saturday=5, Sunday=6
            return False

        # Check if it's between 9:30 AM and 4:00 PM ET, allow 1 minute after market close
        market_open = current_time.replace(
            hour=9, minute=30, second=0, microsecond=0)
        market_close = current_time.replace(
            hour=16, minute=1, second=0, microsecond=0)

        return market_open <= current_time <= market_close

    def _calculate_optimal_sleep_time(self, current_time: datetime) -> float:
        """Calculate optimal sleep time to align with next update opportunity

        This method ensures the thread wakes up at exactly the right time
        for the next bar update, providing precise timing synchronization.
        """
        if not self.intraday_subscriptions:
            return 60.0  # Sleep for 1 minute if no subscriptions

        # Find the next update time for any interval
        next_update_times = []

        for interval in self.intraday_subscriptions.keys():
            next_time = self._get_next_update_time(current_time, interval)
            if next_time:
                next_update_times.append(next_time)

        if not next_update_times:
            return 60.0  # Default to 1 minute if no valid times

        # Find the earliest next update time
        next_update = min(next_update_times)

        # Calculate sleep time
        sleep_seconds = (next_update - current_time).total_seconds()

        # Ensure we don't sleep for negative time
        if sleep_seconds < 0:
            return 1.0  # Sleep for 1 second if we're already past the time

        # Add a small buffer (100ms) to ensure we wake up slightly before the target time
        # This helps compensate for any system scheduling delays
        sleep_seconds = max(0.1, sleep_seconds - 0.1)

        return sleep_seconds + 3

    def _get_next_update_time(self, current_time: datetime, interval: str) -> datetime:
        """Calculate the next update time for a given interval"""
        if interval == '1m':
            # Next minute at :00 seconds
            return current_time.replace(second=0, microsecond=0) + timedelta(minutes=1)

        elif interval == '5m':
            # Next 5-minute boundary (00, 05, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55)
            current_minute = current_time.minute
            next_5min_boundary = ((current_minute // 5) + 1) * 5
            if next_5min_boundary >= 60:
                next_5min_boundary = 0
                return current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            else:
                return current_time.replace(minute=next_5min_boundary, second=0, microsecond=0)

        elif interval == '15m':
            # Next 15-minute boundary (00, 15, 30, 45)
            current_minute = current_time.minute
            next_15min_boundary = ((current_minute // 15) + 1) * 15
            if next_15min_boundary >= 60:
                next_15min_boundary = 0
                return current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            else:
                return current_time.replace(minute=next_15min_boundary, second=0, microsecond=0)

        elif interval == '30m':
            # Next 30-minute boundary (00, 30)
            current_minute = current_time.minute
            if current_minute < 30:
                return current_time.replace(minute=30, second=0, microsecond=0)
            else:
                return current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

        elif interval == '65m':
            # Market session based (09:30, 10:35, 11:40, 12:45, 13:50, 14:55, 16:00)
            return self._get_next_65m_update_time(current_time)

        return current_time + timedelta(minutes=1)  # Default fallback

    def _get_next_65m_update_time(self, current_time: datetime) -> datetime:
        """Calculate next 65m update time based on market session"""
        # Check if we're in a trading day
        if not self._is_trading_day(current_time):
            return self._get_next_trading_day_market_open(current_time)

        # Market hours: 9:30 AM to 4:00 PM
        market_open = current_time.replace(
            hour=9, minute=30, second=0, microsecond=0)
        market_close = current_time.replace(
            hour=16, minute=0, second=0, microsecond=0)

        if current_time < market_open:
            return market_open
        elif current_time >= market_close:
            return self._get_next_trading_day_market_open(current_time)

        # Check if current time aligns with 65-minute boundaries
        elapsed_from_open = current_time - market_open
        elapsed_minutes = elapsed_from_open.total_seconds() / 60

        # 65-minute boundaries: 0, 65, 130, 195, 260, 325 minutes from market open
        if elapsed_minutes % 65 == 0:
            # We're exactly at a boundary, next update in 65 minutes
            return current_time + timedelta(minutes=65)
        else:
            # Calculate next boundary
            next_boundary = ((int(elapsed_minutes) // 65) + 1) * 65
            return market_open + timedelta(minutes=next_boundary)

    def _get_next_trading_day_market_open(self, current_time: datetime) -> datetime:
        """Get next trading day market open (9:30 AM)"""
        next_day = current_time + timedelta(days=1)

        # Skip weekends
        while next_day.weekday() >= 5:  # Saturday=5, Sunday=6
            next_day += timedelta(days=1)

        return next_day.replace(hour=9, minute=30, second=0, microsecond=0)

    def _update_bars_for_interval(self, interval: str):
        """Update bars for a specific interval"""
        tickers = self.intraday_subscriptions.get(interval, set())
        if not tickers:
            return

        try:
            self.logger.debug(
                f"Updating {interval} bars for {len(tickers)} tickers")

            # Fetch bars for all tickers in this interval
            bars_data = self._fetch_intraday_bars(list(tickers), interval)

            # Publish bars to Redis
            self._publish_bars_to_redis(bars_data, interval)

            self.logger.debug(
                f"Successfully updated {interval} bars for {len(tickers)} tickers")

        except Exception as e:
            self.logger.error(f"Error updating {interval} bars: {e}")

    def _fetch_intraday_bars(self, tickers: List[str], interval: str) -> Dict[str, DataFrame]:
        """Fetch intraday bars for multiple tickers"""
        bars_data = {}

        try:
            # Use yf.Tickers for batch fetching
            ticker_objects = yf.Tickers(tickers)
            # Get history for all tickers
            for ticker in tickers:
                try:
                    # For 65m, we need to resample 5m bars
                    if interval == '65m':
                        bars: DataFrame = ticker_objects.tickers[ticker].history(
                            period='1d', interval='5m', actions=False, prepost=False, rounding=True
                        )
                        if not bars.empty:
                            bars = (
                                bars
                                .groupby(bars.index.normalize())
                                .apply(self.resample_session)
                                .droplevel(0)
                                .dropna(how="all")
                            )
                    else:
                        bars: DataFrame = ticker_objects.tickers[ticker].history(
                            period='1d', interval=interval, actions=False, prepost=False, rounding=True
                        )

                    if not bars.empty:
                        bars_data[ticker] = bars

                except Exception as e:
                    self.logger.error(f"Error fetching bars for {ticker}: {e}")

        except Exception as e:
            self.logger.error(f"Error in batch bar fetching: {e}")

        return bars_data

    def _publish_bars_to_redis(self, bars_data: Dict[str, DataFrame], interval: str):
        """Publish bars to Redis for real-time consumption"""
        try:
            for ticker, bars in bars_data.items():
                if bars.empty:
                    continue

                # Get the latest bar
                latest_bar = bars.iloc[-1]
                if latest_bar['Volume'] == 0:
                    latest_bar = bars.iloc[-2]

                # Create bar bars structure
                bar_data = {
                    'ticker': ticker,
                    'interval': interval,
                    'timestamp': int(latest_bar.name.timestamp()) * 1000,
                    'open': float(latest_bar['Open']),
                    'high': float(latest_bar['High']),
                    'low': float(latest_bar['Low']),
                    'close': float(latest_bar['Close']),
                    'volume': int(latest_bar['Volume'])
                }

                # Publish to Redis
                channel = f"bars:{ticker}:{interval}"
                self.redis_client.publish(channel, json.dumps(bar_data))
                self.redis_client.publish(
                    f"bars:latest:{interval}", json.dumps(bar_data))

                # Store latest bar bars
                latest_key = f"bars:latest:{ticker}:{interval}"
                self.redis_client.setex(
                    latest_key, 3600, json.dumps(bar_data))  # Expire in 1 hour

                self.logger.debug(
                    f"Published {interval} bar for {ticker} to Redis")

        except Exception as e:
            self.logger.error(f"Error publishing bars to Redis: {e}")

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

    def get_latest_bar(self, ticker: str, interval: str) -> Dict[str, Any]:
        """Get the latest bar for a specific ticker and interval from Redis"""
        try:
            latest_key = f"bars:latest:{ticker}:{interval}"
            bar_data = self.redis_client.get(latest_key)
            if bar_data:
                if isinstance(bar_data, bytes):
                    bar_data = bar_data.decode('utf-8')
                return json.loads(bar_data)
            return {}
        except Exception as e:
            self.logger.error(
                "Failed to get latest bar for %s:%s from Redis: %s", ticker, interval, e)
            return {}

    def get_active_intraday_tickers(self, interval: str) -> set[str]:
        """Get the set of currently active tickers with intraday bars for a specific interval"""
        try:
            active_key = f"bars:active:{interval}"
            active_tickers = self.redis_client.smembers(active_key)
            return {ticker.decode('utf-8') if isinstance(ticker, bytes) else ticker
                    for ticker in active_tickers}
        except Exception as e:
            self.logger.error(
                f"Failed to get active {interval} tickers from Redis: %s", e)
            return set()

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

    def stop_intraday_bars(self):
        """Stop intraday bar scheduling and cleanup"""
        self._stop_intraday_scheduling()

        # Clear all active bar tickers from Redis
        try:
            for interval in self.supported_intervals:
                self.redis_client.delete(f"bars:active:{interval}")
            self.logger.info("Cleared active bar tickers from Redis")
        except Exception as e:
            self.logger.error(
                "Failed to clear active bar tickers from Redis: %s", e)

        # Clear subscriptions
        self.intraday_subscriptions.clear()
        self.logger.info("Stopped intraday bar subscriptions")

    def __del__(self):
        """Cleanup when object is destroyed"""
        self.stop_live_quotes()
        self.stop_intraday_bars()
