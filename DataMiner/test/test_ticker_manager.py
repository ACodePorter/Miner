import unittest

from detonator import get_logger, make_db_connection

from dataminer import TickerManager

_logger = get_logger('TickerManagerTestCase')


class TickerManagerTestCase(unittest.TestCase):

    def setUp(self):
        make_db_connection(db='mongogo-test')

    def test_get_latest_as_of_date_before(self):
        ticker_manager: TickerManager = TickerManager.get_instance()
        _logger.info(f'latest as of date:{ticker_manager.get_latest_as_of_date_before()}')
        _logger.info(
            f'latest as of date of 20231225:{ticker_manager.get_latest_as_of_date_before("20231227", inclusive=True)}')


if __name__ == '__main__':
    unittest.main()
