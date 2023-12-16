import datetime
import unittest

import pytz

from russell1000miner.datashovel import IsharesShovel
from russell1000miner.utils import get_logger

_logger = get_logger('DataShovelTestCase')


class DataShovelTestCase(unittest.TestCase):
    def test_something(self):
        print(datetime.date.today().strftime('%Y%m%d'))
        shovel = IsharesShovel()
        _logger.info(shovel.get())

    def test_as_of_date(self):
        _logger.info(datetime.datetime.now(
            pytz.timezone('America/New_York')).strftime('%Y%m%d'))
        _logger.info((datetime.datetime.now(pytz.timezone('America/New_York')) - datetime.timedelta(days=1)).strftime(
            '%Y%m%d'))


if __name__ == '__main__':
    tim = None
    count = 0
    import time
    import os
    while time is None and count < 10:
        tim = os.path.getmtime(__file__)
        if not tim:
            time.sleep(10)
            count += 1

    unittest.main()
