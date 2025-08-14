#!/usr/bin/env python3
"""
Example: Intraday Bars Subscription with BarsManager

This example demonstrates how to:
1. Subscribe to intraday bars for multiple tickers and intervals
2. Monitor real-time bar updates via Redis
3. Handle different time intervals (1m, 5m, 15m, 30m, 65m)
4. Clean up subscriptions properly

Usage:
    python example_intraday_bars.py

Requirements:
    - Redis server running
    - yfinance package installed
    - detonator package available
"""

import json
import threading
import time
from datetime import datetime
from typing import Any, Dict

# Import BarsManager
from dataminer import BarsManager


class IntradayBarsExample:
    """Example class demonstrating intraday bars subscription"""

    def __init__(self):
        self.bars_manager = BarsManager()
        self.redis_client = self.bars_manager.redis_client
        self.running = False

        # Sample tickers for demonstration
        self.sample_tickers = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'AMZN']

        # Sample intervals
        self.sample_intervals = ['1m', '5m', '15m', '30m', '65m']

        # Redis pubsub objects for monitoring
        self.pubsub_objects = {}

    def _safe_decode(self, value):
        """Safely decode Redis message values that might be bytes or already strings"""
        if isinstance(value, bytes):
            return value.decode('utf-8')
        elif isinstance(value, str):
            return value
        else:
            return str(value)

    def start_monitoring(self):
        """Start monitoring intraday bars for all tickers and intervals"""
        print("🚀 Starting Intraday Bars Monitoring...")
        print(f"📊 Tickers: {', '.join(self.sample_tickers)}")
        print(f"⏰ Intervals: {', '.join(self.sample_intervals)}")
        print("-" * 60)

        # Subscribe to intraday bars
        self.bars_manager.subscribe_intraday(
            self.sample_tickers, self.sample_intervals)

        # Start monitoring threads for each interval
        self.running = True
        for interval in self.sample_intervals:
            thread = threading.Thread(
                target=self._monitor_interval,
                args=(interval,),
                daemon=True
            )
            thread.start()
            print(f"👁️  Monitoring {interval} bars...")

        # Start monitoring latest bars channel
        latest_thread = threading.Thread(
            target=self._monitor_latest_bars,
            daemon=True
        )
        latest_thread.start()
        print("👁️  Monitoring latest bars channel...")

        print("-" * 60)
        print("✅ Monitoring started! Press Ctrl+C to stop.")

    def _monitor_interval(self, interval: str):
        """Monitor bars for a specific interval"""
        pubsub = None
        try:
            # Subscribe to all tickers for this interval
            pattern = f"bars:*:{interval}"
            pubsub = self.redis_client.pubsub()
            pubsub.psubscribe(pattern)

            print(f"📡 Subscribed to {pattern}")

            for message in pubsub.listen():
                if not self.running:
                    break

                if message['type'] == 'pmessage':
                    channel = self._safe_decode(message['channel'])
                    data = self._safe_decode(message['data'])
                    bar_data = json.loads(data)

                    self._print_bar_update(bar_data, channel)

        except Exception as e:
            print(f"❌ Error monitoring {interval} bars: {e}")
        finally:
            if pubsub:
                pubsub.close()

    def _monitor_latest_bars(self):
        """Monitor the latest bars channel for all intervals"""
        pubsub = None
        try:
            pubsub = self.redis_client.pubsub()
            pubsub.subscribe("bars:latest:1m", "bars:latest:5m", "bars:latest:15m",
                             "bars:latest:30m", "bars:latest:65m")

            print("📡 Subscribed to latest bars channels")

            for message in pubsub.listen():
                if not self.running:
                    break

                if message['type'] == 'message':
                    channel = self._safe_decode(message['channel'])
                    data = self._safe_decode(message['data'])
                    bar_data = json.loads(data)

                    print(f"🆕 LATEST {bar_data['interval']} BAR: {bar_data['ticker']} "
                          f"O:{bar_data['open']:.2f} H:{bar_data['high']:.2f} "
                          f"L:{bar_data['low']:.2f} C:{bar_data['close']:.2f} "
                          f"V:{bar_data['volume']:,}")

        except Exception as e:
            print(f"❌ Error monitoring latest bars: {e}")
        finally:
            if pubsub:
                pubsub.close()

    def _print_bar_update(self, bar_data: Dict[str, Any], channel: str):
        """Print formatted bar update"""
        # Handle timestamp in milliseconds (integer) or ISO string format
        if isinstance(bar_data['timestamp'], (int, float)):
            # Convert milliseconds to seconds for fromtimestamp
            timestamp = datetime.fromtimestamp(bar_data['timestamp'] / 1000)
        else:
            # Handle string timestamps (fallback)
            timestamp = datetime.fromisoformat(bar_data['timestamp'])

        time_str = timestamp.strftime("%H:%M:%S")

        print(f"📊 {time_str} | {bar_data['ticker']} | {bar_data['interval']} | "
              f"O:{bar_data['open']:.2f} H:{bar_data['high']:.2f} "
              f"L:{bar_data['low']:.2f} C:{bar_data['close']:.2f} "
              f"V:{bar_data['volume']:,}")

    def show_active_subscriptions(self):
        """Display current active subscriptions"""
        print("\n📋 Active Subscriptions:")
        print("-" * 40)

        for interval in self.sample_intervals:
            active_tickers = self.bars_manager.get_active_intraday_tickers(
                interval)
            if active_tickers:
                print(f"{interval:>4}: {', '.join(sorted(active_tickers))}")
            else:
                print(f"{interval:>4}: None")

    def show_latest_bars(self):
        """Display latest bars for all tickers and intervals"""
        print("\n📈 Latest Bars:")
        print("-" * 80)
        print(f"{'Ticker':<8} {'Interval':<6} {'Time':<20} {'Open':<8} {'High':<8} {'Low':<8} {'Close':<8} {'Volume':<10}")
        print("-" * 80)

        for ticker in self.sample_tickers:
            for interval in self.sample_intervals:
                bar_data = self.bars_manager.get_latest_bar(ticker, interval)
                if bar_data:
                    # Handle timestamp in milliseconds (integer) or ISO string format
                    if isinstance(bar_data['timestamp'], (int, float)):
                        # Convert milliseconds to seconds for fromtimestamp
                        timestamp = datetime.fromtimestamp(
                            bar_data['timestamp'] / 1000)
                    else:
                        # Handle string timestamps (fallback)
                        timestamp = datetime.fromisoformat(
                            bar_data['timestamp'])

                    time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")

                    print(f"{bar_data['ticker']:<8} {bar_data['interval']:<6} {time_str:<20} "
                          f"{bar_data['open']:<8.2f} {bar_data['high']:<8.2f} "
                          f"{bar_data['low']:<8.2f} {bar_data['close']:<8.2f} "
                          f"{bar_data['volume']:<10,}")
                else:
                    print(
                        f"{ticker:<8} {interval:<6} {'No data':<20} {'N/A':<8} {'N/A':<8} {'N/A':<8} {'N/A':<8} {'N/A':<10}")

    def demonstrate_manual_fetching(self):
        """Demonstrate manual bar fetching for comparison"""
        print("\n🔍 Manual Bar Fetching Example:")
        print("-" * 40)

        ticker = 'AAPL'
        interval = '5m'

        print(f"Fetching {interval} bars for {ticker}...")

        # Get recent bars
        recent_bars = self.bars_manager.get_recent_bars(
            ticker, interval, count=5)
        if not recent_bars.empty:
            print(f"Recent {interval} bars for {ticker}:")
            print(recent_bars.tail())
        else:
            print(f"No {interval} bars available for {ticker}")

        # Get full historical bars
        print(f"\nFetching full historical {interval} bars for {ticker}...")
        historical_bars = self.bars_manager.get_bars(
            ticker, interval, period='5d')
        if not historical_bars.empty:
            print(f"Historical {interval} bars for {ticker} (last 5 days):")
            print(historical_bars.tail())
        else:
            print(f"No historical {interval} bars available for {ticker}")

    def stop_monitoring(self):
        """Stop monitoring and cleanup"""
        print("\n🛑 Stopping monitoring...")
        self.running = False

        # Unsubscribe from intraday bars
        self.bars_manager.unsubscribe_intraday(
            self.sample_tickers, self.sample_intervals)

        # Stop live quotes if any
        self.bars_manager.stop_live_quotes()

        print("✅ Monitoring stopped and cleanup completed")

    def run_demo(self, duration_minutes: int = 5):
        """Run the complete demo for specified duration"""
        try:
            print("🎯 Intraday Bars Subscription Demo")
            print("=" * 60)

            # Start monitoring
            self.start_monitoring()

            # Show initial state
            time.sleep(2)
            self.show_active_subscriptions()

            # Show latest bars
            time.sleep(2)
            self.show_latest_bars()

            # Demonstrate manual fetching
            time.sleep(2)
            self.demonstrate_manual_fetching()

            # Monitor for specified duration
            print(f"\n⏱️  Monitoring for {duration_minutes} minutes...")
            print("Press Ctrl+C to stop early")

            start_time = time.time()
            while time.time() - start_time < duration_minutes * 60 and self.running:
                time.sleep(10)

                # Show status every 30 seconds
                elapsed = int(time.time() - start_time)
                if elapsed % 30 == 0:
                    print(f"⏱️  Elapsed: {elapsed//60}m {elapsed % 60}s")

        except KeyboardInterrupt:
            print("\n\n⏹️  Demo interrupted by user")
        finally:
            self.stop_monitoring()


def main():
    """Main function to run the demo"""
    print("🚀 Starting Intraday Bars Example...")

    # Check if Redis is available
    try:
        bars_manager = BarsManager()
        bars_manager.redis_client.ping()
        print("✅ Redis connection successful")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print("Please ensure Redis server is running")
        return

    # Create and run demo
    demo = IntradayBarsExample()

    try:
        # Run demo for 5 minutes
        demo.run_demo(duration_minutes=5)
    except Exception as e:
        print(f"❌ Demo error: {e}")
        demo.stop_monitoring()


if __name__ == "__main__":
    main()
