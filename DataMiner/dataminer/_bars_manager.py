from datetime import datetime
from typing import Callable, Dict, Literal

import pandas as pd
import yfinance as yf
from detonator import SingletonParent
from pandas import DataFrame


class BarsManager(SingletonParent):
    """
    BarsManager for fetching and managing bar data from yfinance.

    Usage Rules:
    1. get_bars(): Use for fetching full historical data (e.g., initial chart load)
    2. get_recent_bars(): Use for incremental updates and real-time comparison
    """

    def __init__(self):
        self.bars = {}

    def resample_session(self, g: DataFrame) -> DataFrame:
        # Anchor bins at 09:30 for this day
        agg = {
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
        }

        day_midnight = g.index[0].normalize()
        session_start = day_midnight + pd.Timedelta(hours=9, minutes=30)
        return g.resample(
            "65min",
            origin=session_start,
            closed="left",
            label="left",
        ).agg(agg)

    def get_bars(self, ticker: str,
                 interval: Literal['1m', '2m', '5m', '15m', '30m', '65m',
                                   '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo'] = '1d',
                 period: Literal['1d', '5d', '1mo', '3mo', '6mo',
                                 '1y', '2y', '5y', '10y', 'ytd', 'max'] = '1y',
                 start_date: Literal[str, datetime, None] = None) -> DataFrame:
        """ get bars from yfinance

        Args:
            ticker (str): ticker symbol
            interval (Literal['1m', '2m', '5m', '15m', '30m', '65m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo'], optional): interval. Defaults to '1d'.
            period (Literal['1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max'], optional): period. Defaults to '1y'.
            start_date (Literal[str, datetime, None], optional): start date. Defaults to None, if str, it should be in format YYYYMMDD or YYYY-MM-DD.

        Returns:
            DataFrame: bars DataFrame
        """
        # 1-min data; regular trading hours
        resample_bars = interval == '65m'
        interval = '5m' if resample_bars else interval
        period = 'max' if resample_bars else period
        # if start_date is str and in format YYYYMMDD, convert it to YYYY-MM-DD
        if isinstance(start_date, str) and len(start_date) == 8:
            start_date = datetime.strptime(start_date, '%Y%m%d')
        start_date = start_date.strftime(
            '%Y-%m-%d') if isinstance(start_date, datetime) else start_date

        bars = yf.Ticker(ticker).history(
            period=period, interval=interval, start=start_date, actions=False, prepost=False, rounding=True)

        if resample_bars:
            bars = (
                bars
                .groupby(bars.index.normalize())
                .apply(self.resample_session)
                .droplevel(0)
                .dropna(how="all")
            )

        return bars

    def get_recent_bars(self, ticker: str, interval: str, count: int = 10) -> DataFrame:
        """Get the most recent bars for incremental updates and comparison

        Args:
            ticker (str): ticker symbol
            interval (str): interval string
            count (int): number of recent bars to return

        Returns:
            DataFrame: recent bars DataFrame optimized for incremental updates
        """
        # For minute intervals, get enough data to ensure we have current session
        if interval in ['1m', '2m', '5m', '15m', '30m', '65m', '90m', '1h']:
            period = '1d'  # Get 1 day for current session data
        else:
            period = '3d'  # Get 3 days for daily/weekly data

        bars = self.get_bars(ticker, interval, period)
        if bars.empty:
            return bars

        # Return the last N bars for incremental comparison
        return bars.tail(count)
