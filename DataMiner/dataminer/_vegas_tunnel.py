import logging
from typing import Dict, List, Literal, Optional

import numpy as np
from detonator import SingletonParent, get_logger
from detonator.types import IntradayInterval
from pandas import DataFrame

from ._market_data_shovel import MarketDataShovel


class VegasTunnel(SingletonParent):
    EMA_SPANS = [10, 12, 20, 144, 169, 576, 676]

    def __init__(self):
        super().__init__()
        self.logger = get_logger('VegasTunnel', logging.DEBUG)

    def _prepare_data(self, tickers: str | List[str],
                      intervals: IntradayInterval = '65m') -> Dict[
            str, Dict[str, DataFrame]]:
        if isinstance(tickers, str):
            tickers = [tickers]
        if isinstance(intervals, str):
            intervals = [intervals]
        mds: MarketDataShovel = MarketDataShovel.get_instance()
        full_bars: Dict[str, Dict[str, DataFrame]
                        ] = mds.get_intraday_bars(tickers, intervals)

        self.logger.debug(f'Raw bars shape: {len(full_bars)}')

        for interval, ticker_bars in full_bars.items():
            self.logger.debug(f'Interval: {interval}')
            for ticker, bars in ticker_bars.items():
                if bars.empty:
                    self.logger.warning(f'No intraday bars for {ticker}')
                    continue
                self.logger.debug(
                    f'Ticker: {ticker}:{bars.shape} ->\n{bars.head(1)}\n{bars.tail(1)}')
                for span in VegasTunnel.EMA_SPANS:
                    bars[f'ema{span}'] = bars['close'].ewm(
                        span=span, adjust=False, min_periods=1).mean()
                # Only drop rows where essential columns are NaN, not EMA columns
                bars.dropna(how='any', inplace=False)

        return full_bars

    def _vegas_double_tunnel_signals(self, bars: DataFrame) -> DataFrame:
        """
        Generates trading signals for the Vegas Double Tunnel strategy using a vectorized approach.

        This function calculates the short-term and long-term EMA tunnels and a fast-moving EMA filter
        to identify potential 'buy' and 'sell' entry signals, as well as 'increase' and 'decrease'
        signals for position management. The logic is based on the Double Tunnel variant of the
        Vegas strategy.

        Args:
            bars: A pandas DataFrame with at least 'open', 'high', 'low', and 'close' columns.

        Returns:
            A pandas DataFrame with the original bars plus new columns:
            - 'short_term_tunnel_upper': The upper boundary of the short-term tunnel.
            - 'short_term_tunnel_lower': The lower boundary of the short-term tunnel.
            - 'long_term_trend': An integer representing the long-term trend (1 for bullish, -1 for bearish, 0 for neutral).
            - 'signal': An integer representing the trading signal on a specific bar:
                - 1: Buy (New long position entry).
                - 2: Increase (Add to an existing long position).
                - -1: Sell (New short position entry).
                - -2: Decrease (Add to an existing short position).
                - 0: No action.
        """
        required_cols = ['open', 'high', 'low', 'close']
        if not all(col in bars.columns for col in required_cols):
            raise ValueError(
                f"Input DataFrame must contain {required_cols} columns.")

        # --- 1. Vectorized Calculation of All EMAs ---
        # we already prepared bars, do not calculate here

        # Define the short-term tunnel boundaries
        bars['short_term_tunnel_upper'] = bars[[
            'ema144', 'ema169']].max(axis=1)
        bars['short_term_tunnel_lower'] = bars[[
            'ema144', 'ema169']].min(axis=1)

        # Define the long-term trend based on the EMA 576/676 relationship
        # 1 long, -1 short, 0 none
        bars['long_term_trend'] = np.where(bars['ema576'] > bars['ema676'], 1,
                                           np.where(bars['ema576'] < bars['ema676'], -1, 0))

        # close_to_filter, close relation to filter line(ema12) , 1:above, 0:equal, -1:bellow
        bars['close_to_filter'] = np.where(bars['close'] > bars['ema12'], 1,
                                           np.where(bars['close'] < bars['ema12'], -1, 0))
        # cross_filter:how close close cross filter line,  1 up cross, -1, down cross, 0 no cross
        bars['close_cross_filter'] = (
            bars['close_to_filter'] - bars['close_to_filter'].shift(1).bfill()).astype(np.int64)

        # filter_to_short_uppper
        bars['filter_to_short_upper'] = np.where(bars['ema12'] > bars['short_term_tunnel_upper'], 1,
                                                 np.where(bars['ema12'] < bars['short_term_tunnel_upper'], -1, 0))
        bars['filter_cross_short_upper'] = (
            bars['filter_to_short_upper'] - bars['filter_to_short_upper'].shift(1).bfill()).astype(np.int64)

        # filter_to_short_lower
        bars['filter_to_short_lower'] = np.where(bars['ema12'] < bars['short_term_tunnel_lower'], 1,
                                                 np.where(bars['ema12'] > bars['short_term_tunnel_lower'], -1, 0))
        bars['filter_cross_short_lower'] = (
            bars['filter_to_short_lower'] - bars['filter_to_short_lower'].shift(1).bfill()).astype(np.int64)

        # --- 2. Vectorized Signal Generation ---
        # Use np.where for fast, vectorized conditional logic. This is much faster than a for loop.

        # Long Breakout Entry: Price & EMA12 break above the short-term tunnel, and long-term trend is bullish.
        long_breakout = (bars['close'] > bars['short_term_tunnel_upper']) & \
                        (bars['ema12'] > bars['short_term_tunnel_upper']) & \
                        (bars['long_term_trend'] == 1)

        # Short Breakout Entry: Price & EMA12 break below the short-term tunnel, and long-term trend is bearish.
        short_breakout = (bars['close'] < bars['short_term_tunnel_lower']) & \
                         (bars['ema12'] < bars['short_term_tunnel_lower']) & \
                         (bars['long_term_trend'] == -1)

        # Long Pullback/Retest Entry: Price 'bounces' off the upper side of the short-term tunnel.
        # We require a low touching the tunnel and a close above it to simulate a bounce.
        long_retest = (bars['low'] <= bars['short_term_tunnel_upper']) & \
                      (bars['close'] > bars['short_term_tunnel_upper']) & \
                      (bars['long_term_trend'] == 1) & \
                      (bars['close'].shift(1) > bars['short_term_tunnel_upper'].shift(
                          1))  # Ensure we are already in a trend

        # Short Pullback/Retest Entry: Price 'bounces' off the lower side of the short-term tunnel.
        # We require a high touching the tunnel and a close below it to simulate a bounce.
        short_retest = (bars['high'] >= bars['short_term_tunnel_lower']) & \
                       (bars['close'] < bars['short_term_tunnel_lower']) & \
                       (bars['long_term_trend'] == -1) & \
                       (bars['close'].shift(1) < bars['short_term_tunnel_lower'].shift(
                           1))  # Ensure we are already in a trend

        # Assign signals based on the logic. 'buy' is a new entry, 'increase' is for adding to a position.
        # bars['signal'] = np.where(long_breakout, 1, np.where(short_breakout, -1, 0))
        bars['vegas_signal'] = np.where(bars['filter_cross_short_upper'] == 2, 2,
                                        np.where(bars['filter_cross_short_upper'] == 1, 1, 0))

        # Overwrite signals for retest entries. This is a common way to signal continuation.
        bars['vegas_signal'] = np.where(bars['filter_cross_short_lower'] == 2, -2,
                                        np.where(bars['filter_cross_short_lower'] == 1, -1, bars['vegas_signal']))

        # Clean up intermediate columns to keep the output clean
        bars.drop(columns=['short_term_tunnel_upper', 'short_term_tunnel_lower', 'long_term_trend', 'close_to_filter',
                           'close_cross_filter', 'filter_to_short_upper', 'filter_cross_short_upper',
                           'filter_to_short_lower', 'filter_cross_short_lower'], inplace=True)

        return bars

    def _update_wedge_signals(self, bars: Optional[DataFrame]) -> Optional[DataFrame]:
        '''
        lets do a simplified wedge pop/drop check for short term buy/sell
        '''
        if bars is None or bars.empty:
            self.logger.warning(f"Invalid DataFrame: {bars}")
            return bars
        bars['ema_diff'] = bars['ema10'] - bars['ema20']
        # Calculate slope of EMA difference using polynomial fitting over a rolling window
        bars['ema_diff_slope'] = bars['ema_diff'].rolling(window=3).apply(
            lambda x: np.polyfit(range(len(x)), x, 1)[
                0] if len(x) >= 3 else np.nan
        )
        bars['is_above_emas'] = (bars['close'] > bars['ema10']) & (
            bars['close'] > bars['ema20'])
        bars['is_below_any_emas'] = (bars['close'] < bars['ema10']) | (
            bars['close'] < bars['ema20'])
        bars['was_below_emas'] = bars['is_below_any_emas'].shift(1).bfill()
        bars['is_below_emas'] = (bars['close'] < bars['ema10']) & (
            bars['close'] < bars['ema20'])
        bars['is_above_any_emas'] = (bars['close'] > bars['ema10']) | (
            bars['close'] > bars['ema20'])
        bars['was_above_emas'] = bars['is_above_any_emas'].shift(1).bfill()
        bars['wedge_signal'] = np.where(
            bars['is_above_emas'] & bars['was_below_emas'] & (
                bars['ema_diff_slope'] > 0), 1,
            np.where(bars['is_below_emas'] & bars['was_above_emas'] & (bars['ema_diff_slope'] < 0), -1, 0))
        return bars.drop(columns=['ema_diff', 'ema_diff_slope', 'is_above_emas', 'is_below_any_emas', 'was_below_emas',
                                  'is_below_emas', 'is_above_any_emas',
                                  'was_above_emas'])

    def update_signals(self, tickers: str | List[str],
                       intervals: Literal['5m', '10m', '15m', '30m', '65m'] | List[str]) -> Dict[
            str, Dict[str, DataFrame]]:
        batch_size = 110
        if isinstance(tickers, str):
            tickers = [tickers]
        if isinstance(intervals, str):
            intervals = [intervals]
        self.logger.info('%s %s', tickers, intervals)
        full_bars: Dict[str, Dict[str, DataFrame]] = {
            interval: {} for interval in intervals}
        for i in range(0, len(tickers), batch_size):
            batch_tickers = tickers[i:i + batch_size]
            batch_bars: Dict[str, Dict[str, DataFrame]
                             ] = self._prepare_data(batch_tickers, intervals)
            for interval, ticker_bars in batch_bars.items():
                for ticker, bars in ticker_bars.items():
                    signal_bars = self._vegas_double_tunnel_signals(bars)
                    signal_bars = self._update_wedge_signals(signal_bars)
                    batch_bars[interval][ticker] = signal_bars
                full_bars[interval] |= batch_bars[interval]
        return full_bars
