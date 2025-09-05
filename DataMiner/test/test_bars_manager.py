from datetime import datetime, timedelta
from unittest import TestCase

import pandas as pd
from dataminer import BarsManager
from detonator import get_redis_client


class BarsManagerTestCase(TestCase):
    def setUp(self):
        try:
            self.redis_client = get_redis_client()
            self.redis_client.ping()
        except Exception as e:
            print(f"Error connecting to Redis: {e}")
            self.fail(f"Error connecting to Redis: {e}")

    def test_get_bars(self):
        bars_manager = BarsManager.get_instance()
        bars = bars_manager.get_bars('AAPL', '1d', '1y')
        print(bars.head())
        print(bars.tail())
        self.assertIsInstance(bars, pd.DataFrame)
        bars = bars_manager.get_bars('AAPL', '65m')
        print(bars.head())
        print(bars.tail())
        self.assertIsInstance(bars, pd.DataFrame)
        bars = bars_manager.get_bars('AAPL', '1m', '1d')
        print(bars.head())
        print(bars.tail())
        self.assertIsInstance(bars, pd.DataFrame)
        bars = bars_manager.get_bars('AAPL', '1d', '1y', '2024-01-01')
        print(bars.head())
        print(bars.tail())
        self.assertIsInstance(bars, pd.DataFrame)

    def test_timing_logic(self):
        """Test the timing logic for different intervals"""
        bars_manager = BarsManager.get_instance()

        # Test with a known time (e.g., 10:00:03 AM)
        from datetime import datetime

        import pytz

        # Create a test time: 10:00:03 AM ET on a weekday
        test_time = datetime.now(pytz.timezone('America/New_York')).replace(
            hour=10, minute=0, second=3, microsecond=0
        )

        # For 1m interval at 10:00:03, should return True (within 5 second tolerance)
        is_update_time = bars_manager.test_timing_logic(test_time, '1m')
        print(
            f"1m interval at {test_time.strftime('%H:%M:%S')}: {is_update_time}")
        self.assertTrue(
            is_update_time, "1m interval should allow updates within 5 seconds of :00")

        # For 5m interval at 10:00:03, should return True (at :00 with 3 seconds)
        is_update_time = bars_manager.test_timing_logic(test_time, '5m')
        print(
            f"5m interval at {test_time.strftime('%H:%M:%S')}: {is_update_time}")
        self.assertTrue(
            is_update_time, "5m interval should allow updates at :00 with 3 seconds")

        # Test at 10:01:07 (should not allow updates for 1m or 5m)
        test_time_2 = test_time.replace(minute=1, second=7)
        is_update_time_1m = bars_manager.test_timing_logic(test_time_2, '1m')
        is_update_time_5m = bars_manager.test_timing_logic(test_time_2, '5m')
        print(
            f"1m interval at {test_time_2.strftime('%H:%M:%S')}: {is_update_time_1m}")
        print(
            f"5m interval at {test_time_2.strftime('%H:%M:%S')}: {is_update_time_5m}")
        self.assertFalse(is_update_time_1m,
                         "1m interval should not allow updates at :07")
        self.assertFalse(is_update_time_5m,
                         "5m interval should not allow updates at :07")

    def test_subscribe_intraday(self):
        bars_manager = BarsManager.get_instance()

        # Subscribe to intraday bars
        bars_manager.subscribe_intraday('QQQ', '1m')
        bars_manager.subscribe_intraday('QQQ', '5m')
        bars_manager.subscribe_intraday('QQQ', '15m')
        bars_manager.subscribe_intraday('QQQ', '30m')
        bars_manager.subscribe_intraday('QQQ', '65m')

        bars_manager.subscribe_intraday('NVDA', '1m')
        bars_manager.subscribe_intraday('NVDA', '5m')
        bars_manager.subscribe_intraday('NVDA', '15m')
        bars_manager.subscribe_intraday('NVDA', '30m')
        bars_manager.subscribe_intraday('NVDA', '65m')

        # Wait a moment for the subscription to be processed
        import time
        time.sleep(2)

        # Check if the subscription was properly set up
        active_tickers = bars_manager.get_active_intraday_tickers('1m')
        print(f"Active 1m tickers: {active_tickers}")
        self.assertIn('QQQ', active_tickers)

        # Set up Redis subscription to monitor for bar updates
        pubsub = self.redis_client.pubsub()
        pubsub.subscribe('bars:QQQ:1m')
        pubsub.subscribe('bars:QQQ:5m')
        pubsub.subscribe('bars:QQQ:15m')
        pubsub.subscribe('bars:QQQ:30m')
        pubsub.subscribe('bars:QQQ:65m')

        pubsub.subscribe('bars:NVDA:1m')
        pubsub.subscribe('bars:NVDA:5m')
        pubsub.subscribe('bars:NVDA:15m')
        pubsub.subscribe('bars:NVDA:30m')
        pubsub.subscribe('bars:NVDA:65m')

        # Wait for the first message to confirm subscription
        start_time = datetime.now()
        message_received = False

        # Monitor for up to 2 minutes (should get at least one update)
        while datetime.now() - start_time < timedelta(seconds=1200):
            for message in pubsub.listen():
                print(f"================== Received message: {message}")
                if message['type'] == 'message':
                    message_received = True
                    print(f"        ========== Bar bars: {message['bars']}")
                    break
            time.sleep(1)

        # Clean up
        bars_manager.unsubscribe_intraday('QQQ', '1m')
        pubsub.unsubscribe('bars:QQQ:1m')
        pubsub.close()

        # Verify unsubscription worked
        active_tickers_after = bars_manager.get_active_intraday_tickers('1m')
        print(f"Active 1m tickers after unsubscribe: {active_tickers_after}")
        self.assertNotIn('QQQ', active_tickers_after)

        # Assert that we received at least one message
        self.assertTrue(
            message_received, "No bar update messages were received within 2 minutes")


if __name__ == '__main__':
    import unittest
    unittest.main()
