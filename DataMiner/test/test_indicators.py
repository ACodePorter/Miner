import unittest

from dataminer import Indicators
from detonator import make_db_connection, get_logger

_l = get_logger('IndicatorsTestCase')


class IndicatorsTestCase(unittest.TestCase):
    make_db_connection()

    def test_update_spx_daily_sma(self):
        indicators: Indicators = Indicators.get_instance()
        ret = indicators.update_spx_daily_sma()
        _l.debug(ret)


if __name__ == '__main__':
    unittest.main()
