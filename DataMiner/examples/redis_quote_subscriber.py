#!/usr/bin/env python3
"""
Redis Quote Subscriber Example

This script demonstrates how to subscribe to live quotes published by BarsManager
via Redis pub/sub channels.
"""

import json
import sys
from typing import List

from detonator import get_logger, get_redis_client

from dataminer import BarsManager


class RedisQuoteSubscriber:
    """Subscribe to live quotes from BarsManager via Redis"""

    def __init__(self):
        self.redis_client = get_redis_client()
        self.logger = get_logger('RedisQuoteSubscriber')
        self.pubsub = self.redis_client.pubsub()
        self.bars_manager = BarsManager.get_instance()

    def subscribe_to_tickers(self, tickers: List[str]):
        """Subscribe to specific ticker quote channels"""
        channels = [f"quotes:{ticker.upper()}" for ticker in tickers]
        channels.append('quote:latest')
        self.bars_manager.subscribe(tickers)
        self.pubsub.subscribe(*channels)
        self.logger.info("Subscribed to channels: %s", channels)

    def listen_for_quotes(self, timeout: int = 30):
        """Listen for incoming quotes using Redis pub/sub listen() method"""
        self.logger.info(
            "Listening for quotes (timeout: %d seconds)...", timeout)
        try:
            # Use listen() method for real-time message reception
            for message in self.pubsub.listen():
                if message and message.get('type') == 'message':
                    channel = message.get('channel')
                    data = message.get('bars')

                    if not channel or not data:
                        continue

                    # Decode bars if it's bytes
                    if isinstance(data, bytes):
                        data = data.decode('utf-8')

                    # Parse JSON bars
                    try:
                        quote = json.loads(data)
                        print(f"  Quote: {quote}")
                        print(f"  Channel: {channel}")
                    except json.JSONDecodeError:
                        self.logger.error(
                            "Failed to parse quote bars: %s", data)

        except KeyboardInterrupt:
            self.logger.info("Interrupted by user")
        except Exception as e:
            self.logger.error("Error processing message: %s", e)
        finally:
            self.bars_manager.stop_live_quotes()

        self.logger.info("Finished listening for quotes")

    def get_active_tickers(self) -> List[str]:
        """Get list of currently active tickers with live quotes"""
        try:
            active_tickers = self.redis_client.smembers("quotes:active")
            return [ticker.decode('utf-8') if isinstance(ticker, bytes) else ticker
                    for ticker in active_tickers]
        except Exception as e:
            self.logger.error("Failed to get active tickers: %s", e)
            return []

    def close(self):
        """Close the Redis pub/sub connection"""
        if self.pubsub:
            self.pubsub.close()
        self.logger.info("Redis connection closed")


def main():
    """Main function to run the quote subscriber"""
    if len(sys.argv) < 2:
        print(
            "Usage: python redis_quote_subscriber.py [ticker1] [ticker2] ...")
        print("Example: python redis_quote_subscriber.py AAPL MSFT")
        sys.exit(1)

    tickers = sys.argv[1:]
    subscriber = RedisQuoteSubscriber()

    try:
        # Show active tickers
        active_tickers = subscriber.get_active_tickers()
        print(f"Currently active tickers: {active_tickers}")

        # Subscribe to specified tickers
        subscriber.subscribe_to_tickers(tickers)

        # Listen for quotes
        subscriber.listen_for_quotes()

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        subscriber.close()


if __name__ == "__main__":
    main()
