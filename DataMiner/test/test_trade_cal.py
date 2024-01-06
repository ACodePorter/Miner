import unittest

from detonator import get_logger

from dataminer import TradeCalendarShovel

_logger = get_logger('TradeCalTestCase')


class TradeCalTestCase(unittest.TestCase):
    def test_is_today_us_trade_day(self):
        tcs = TradeCalendarShovel.get_instance()
        _logger.info(f'is_today_us_trade_day:{tcs.is_today_us_trade_day()}')

    def test_last_us_trade_day_before_today(self):
        tcs = TradeCalendarShovel.get_instance()
        _logger.info(tcs.last_us_trade_day_before_today())


if __name__ == '__main__':
    unittest.main()
