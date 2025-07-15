#!/usr/bin/env python3
"""
Example script demonstrating how to use the optimized historical trade calendar function.
This script shows how to fetch historical trading calendar data efficiently in chunks.
"""

from dataminer import TradeCalendarShovel
from detonator import get_logger, make_db_connection
import time
import sys
import os

# Add the parent directory to the path so we can import dataminer
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


_logger = get_logger('HistoricalTradeCalExample')


def main():
    """Main function to demonstrate optimized historical trade calendar functionality"""

    # Initialize database connection
    make_db_connection()

    # Get the TradeCalendarShovel instance
    tcs = TradeCalendarShovel.get_instance()

    # time.sleep(65)
    result = tcs.update_historical_us_trade_calendar("19620101", "20250712")
    # result = tcs.update_historical_us_trade_calendar("19780607", "20091231")
    end_time = time.time()
    print(f"Time taken: {end_time - start_time} seconds")
    if result:
        print("   ✓ Successfully updated historical trade calendar data for 2000")
    else:
        print("   ✗ Failed to update historical trade calendar data for 2000")
        return


if __name__ == '__main__':
    main()
