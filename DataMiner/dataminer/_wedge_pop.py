import logging
from datetime import datetime
from typing import List, Literal, Optional

import numpy as np
import pandas as pd
import pytz
from detonator import (SingletonParent, get_logger, make_db_connection,
                       mongo_2_df, run_parallel)
from pandas import DataFrame
from scipy.signal import find_peaks

from ._market_data_shovel import MarketDataShovel
from ._trade_cal import TradeCalendarShovel
from .models import TickerDailyInfo

_l = get_logger('WedgePop', level=logging.INFO)


class WedgeConfig:
    MIN_WEDGE_LEN = 3
    MAX_WEDGE_LEN = 15
    PEAK_DISTANCE = 3
    R_SQUARED_THRESHOLD = 0.75
    MIN_RELATIVE_VOLUME = 1.5
    ATR_PERIOD = 5
    VOLUME_ROLLING_WINDOW = 22
    BACKWARD_LOOKBACK_VOLUME_WINDOW = 22


class WedgePop(SingletonParent):

    def _prepare_data(self, ticker: str) -> DataFrame:
        try:
            make_db_connection()
            ticker_info = TickerDailyInfo.objects(
                ticker=ticker, interval='1d', wedge_status__exists=True)
            if ticker_info.count() == 0:
                # Get all records ordered by trade_date for new tickers
                ticker_daily_info_list = TickerDailyInfo.objects(
                    ticker=ticker, interval='1d').order_by('trade_date')
            else:
                # Get the latest record with wedge_status
                latest_with_wedge = TickerDailyInfo.objects(
                    ticker=ticker, interval='1d', wedge_status__exists=True).order_by('-trade_date').limit(1).first()
                if latest_with_wedge is None:
                    _l.error(f"No latest with wedge found for ticker {ticker}")
                    return DataFrame()
                earliest_for_calculation = TickerDailyInfo.objects(ticker=ticker, interval='1d', trade_date__lte=latest_with_wedge.trade_date).order_by(
                    '-trade_date').skip(WedgeConfig.VOLUME_ROLLING_WINDOW*2).limit(1).first()
                if earliest_for_calculation is None:
                    _l.error(
                        f"No earliest for calculation found for ticker {ticker}")
                    return DataFrame()
                ticker_daily_info_list = TickerDailyInfo.objects(
                    ticker=ticker, interval='1d', trade_date__gte=earliest_for_calculation.trade_date).order_by('trade_date')

            data = mongo_2_df(ticker_daily_info_list)
            if data.empty:
                _l.error(f"No data found for ticker {ticker}")
                return DataFrame()
            data = data[['_id', 'trade_date', 'ticker', 'open', 'high',
                         'low', 'close', 'volume', 'ema10', 'ema20']]
            _l.debug(f'data:\n{data}\n')
            return data
        except Exception as e:
            _l.error(f"Error preparing data for ticker {ticker}: {str(e)}")
            return DataFrame()

    def _preprocess_data(self, data: DataFrame) -> DataFrame:
        # --- Indicator Calculations ---
        # Average volume calculation.
        data['avg_volume'] = data['volume'].rolling(
            window=WedgeConfig.VOLUME_ROLLING_WINDOW).mean()

        # --- Calculate Average True Range (ATR) for Volatility/Risk ---
        # ATR is a measure of volatility. It helps assess risk for setting stop-losses.
        high_low = data['high'] - data['low']
        high_close = np.abs(data['high'] - data['close'].shift())
        low_close = np.abs(data['low'] - data['close'].shift())

        # Calculate True Range as the maximum of the three ranges
        true_range = pd.concat(
            [high_low, high_close, low_close], axis=1).max(axis=1)

        # Calculate ATR using exponential moving average
        data['atr'] = true_range.ewm(
            alpha=1/WedgeConfig.ATR_PERIOD, adjust=False).mean()

        data['atr_slope'] = data['atr'].rolling(window=3).apply(
            lambda x: np.polyfit(range(len(x)), x, 1)[
                0] if len(x) >= 3 else np.nan
        )

        data['ema_diff'] = data['ema10'] - data['ema20']
        # Calculate slope of EMA difference using polynomial fitting over a rolling window
        data['ema_diff_slope'] = data['ema_diff'].rolling(window=3).apply(
            lambda x: np.polyfit(range(len(x)), x, 1)[
                0] if len(x) >= 3 else np.nan
        )
        data['is_above_emas'] = (data['close'] > data['ema10']*0.995) & (
            data['close'] > data['ema20']*0.995)
        data['was_below_emas'] = (data['close'].shift(1) < data['ema10'].shift(1)*1.005) | (
            data['close'].shift(1) < data['ema20'].shift(1)*1.005)
        data['is_below_emas'] = (data['close'] < data['ema10']*1.005) & (
            data['close'] < data['ema20']*1.005)
        data['was_above_emas'] = (data['close'].shift(1) > data['ema10'].shift(1)*0.995) | (
            data['close'].shift(1) > data['ema20'].shift(1)*0.995)
        data['is_high_rvol'] = data['volume'] / \
            data['avg_volume'] >= WedgeConfig.MIN_RELATIVE_VOLUME
        return data

    def _is_wedge_pop(self, is_above_emas: bool, was_below_emas: bool, ema_diff_slope: float, volume_increased: bool, atr_slope: float) -> bool:
        return is_above_emas and was_below_emas and ema_diff_slope > 0 and volume_increased and atr_slope < 0

    def _is_wedge_drop(self, is_below_emas: bool, was_above_emas: bool, ema_diff_slope: float, volume_increased: bool, atr_slope: float) -> bool:
        return is_below_emas and was_above_emas and ema_diff_slope < 0 and volume_increased

    def update_wedge_pop(self, ticker: str) -> bool:
        data: DataFrame = self._prepare_data(ticker)
        if data.empty or len(data) < 2*WedgeConfig.VOLUME_ROLLING_WINDOW:
            _l.error(f"No enough data found for ticker {ticker}")
            return False
        data: DataFrame = self._preprocess_data(data)
        if data.empty or len(data) < 2*WedgeConfig.VOLUME_ROLLING_WINDOW:
            _l.error(f"No valid data for ticker {ticker}")
            return False
        for i in range(2*WedgeConfig.VOLUME_ROLLING_WINDOW, len(data)):
            _l.debug(
                f'i: {data.iloc[i]["ticker"]} on {data.iloc[i]["trade_date"]}')
            wedge_window = data.iloc[i -
                                     WedgeConfig.BACKWARD_LOOKBACK_VOLUME_WINDOW + 1: i + 1]
            vol_high_idx, _ = find_peaks(
                wedge_window['volume'], distance=WedgeConfig.BACKWARD_LOOKBACK_VOLUME_WINDOW)
            vol_increased = False
            for idx in vol_high_idx:
                if (wedge_window['volume'].iloc[idx] / wedge_window['avg_volume'].iloc[idx]) >= 1.5:
                    vol_increased = True
                    break
            vol_increased = (
                data['volume'].iloc[i] / data['avg_volume'].iloc[i] >= 1.5 or vol_increased)
            _l.debug(
                f'{data.iloc[i].to_dict()} vol_increased: {vol_increased}')
            if self._is_wedge_pop(data['is_above_emas'].iloc[i], data['was_below_emas'].iloc[i], data['ema_diff_slope'].iloc[i], vol_increased, data['atr_slope'].iloc[i]):
                data.loc[i, 'wedge_status'] = 'pop'
            elif self._is_wedge_drop(data['is_below_emas'].iloc[i], data['was_above_emas'].iloc[i], data['ema_diff_slope'].iloc[i], vol_increased, data['atr_slope'].iloc[i]):
                data.loc[i, 'wedge_status'] = 'drop'
            else:
                data.loc[i, 'wedge_status'] = 'none'
            TickerDailyInfo.objects(ticker=ticker, interval='1d', id=(data['_id'].iloc[i])['$oid']).update(
                wedge_status=data['wedge_status'].iloc[i])
        data.to_csv(f'{ticker}_wedge_pop.csv', index=False)
        return True  # Return True to indicate successful processing

    def update_wedge_pop_for_index(self, idx: Literal['spx', 'iwd', 'iwf', 'iwm']) -> bool:
        md: MarketDataShovel = MarketDataShovel.get_instance()
        tickers: List[str] = md.get_latest_index_tickers(idx).tickers
        results: List[bool] = run_parallel(self.update_wedge_pop, tickers)
        _l.debug(f'results: {all(results)}')
        return all(results)

    def get_wedge_tickers_on(self, day: str | datetime) -> List[str]:
        make_db_connection()
        cal = TradeCalendarShovel.get_instance()
        day = cal.get_last_closed_trade_date_before(
            day, country='us', exchange='XNYS')
        tickers: List[str] = TickerDailyInfo.objects(
            wedge_status__in=['pop', 'drop'], trade_date=datetime.strptime(day, '%Y%m%d')).distinct('ticker')
        return tickers

    def get_wedge_tickers_on_today(self) -> List[str]:
        return self.get_wedge_tickers_on(datetime.now(tz=pytz.timezone('America/New_York')))

    def get_wedge_tickers_since(self, start_date: str | datetime, end_date: Optional[str | datetime] = None) -> List[str]:
        if end_date is None:
            end_date = datetime.now(tz=pytz.timezone('America/New_York'))
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y%m%d')
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y%m%d')
        tickers: List[str] = TickerDailyInfo.objects(
            wedge_status__in=['pop', 'drop'], trade_date__gte=start_date, trade_date__lte=end_date).distinct('ticker')
        return tickers
