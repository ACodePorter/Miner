import datetime
import unittest

from detonator import get_logger, make_db_connection

from dataminer import IsharesShovel

_logger = get_logger('DataShovelTestCase')


class DataShovelTestCase(unittest.TestCase):

    def setUp(self):
        make_db_connection()

    def test_ishare_shovel(self):
        print(datetime.date.today().strftime('%Y%m%d'))
        shovel: IsharesShovel = IsharesShovel.get_instance()
        _logger.info(shovel.update_russell1000_tickers_from_ishare_2_db())


if __name__ == '__main__':
    unittest.main()
