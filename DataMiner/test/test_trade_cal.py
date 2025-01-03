import unittest

from detonator import get_logger, make_db_connection

from dataminer import TradeCalendarShovel

_logger = get_logger('TradeCalTestCase')


class TradeCalTestCase(unittest.TestCase):

    def setUp(self):
        make_db_connection(db='mongogo-test')

    def test_is_today_us_trade_day(self):
        tcs = TradeCalendarShovel.get_instance()
        _logger.info(f'is_today_us_trade_day:{tcs.is_today_us_trade_day()}')

    def test_last_us_trade_day_before_today(self):
        tcs = TradeCalendarShovel.get_instance()
        _logger.info(tcs.last_us_trade_day_before_today())

    def test_us_trade_dates_since(self):
        tcs = TradeCalendarShovel.get_instance()
        _logger.info(tcs.us_trade_dates_since('20231223', '20240102'))
        _logger.info(tcs.us_trade_dates_since('20241230'))

    def test_update_us_trade_calendar(self):
        tcs: TradeCalendarShovel = TradeCalendarShovel.get_instance()
        tcs.update_us_trade_calendar()

    def test_last_closed_us_trade_date(self):
        tcs: TradeCalendarShovel = TradeCalendarShovel.get_instance()
        _logger.info(tcs.last_closed_us_trade_date())
        from datetime import datetime
        _logger.info(f'{datetime.now().hour}')


if __name__ == '__main__':
    unittest.main()
