from unittest import TestCase

import pandas as pd
from dataminer import BarsManager


class BarsManagerTestCase(TestCase):
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
