from typing import Dict
from unittest import TestCase

import mplfinance as mpf
import numpy as np
import pandas as pd
from detonator import make_db_connection
from mongoengine import disconnect_all
from pandas import DataFrame

from dataminer import VegasTunnel, MarketDataShovel


def plot_vegas_double_tunnel_signals(df: pd.DataFrame, title: str = 'Vegas Double Tunnel Strategy'):
    """
    Plots a candlestick chart with Vegas Double Tunnel EMAs and trade signals.

    Args:
        df: A pandas DataFrame containing OHLC bars and columns for the Vegas Tunnel EMAs
            and a 'signal' column with integer values.
        title: The title of the plot.
    """
    if df.empty:
        print("Warning: Cannot plot empty DataFrame")
        return

    if 'vegas_signal' not in df.columns:
        raise ValueError("Input DataFrame must have a 'signal' column from the strategy function.")

    # Convert timestamp to datetime and set as index for mplfinance
    # df.index = pd.to_datetime(df['timestamp'])

    # Prepare bars for mplfinance. Columns must be capitalized.
    df_plot = df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'})

    # --- 1. Prepare additional plots for EMAs and signals ---

    # EMAs as a list of additional plots
    apds = [
        mpf.make_addplot(df_plot['ema12'], color='blue', linestyle='--', label='EMA 12'),
        mpf.make_addplot(df_plot['ema10'], color='green', linestyle='--', label='EMA 10'),
        mpf.make_addplot(df_plot['ema20'], color='blue', linestyle='--', label='EMA 20'),
        mpf.make_addplot(df_plot['ema144'], color='lime', label='EMA 144'),
        mpf.make_addplot(df_plot['ema169'], color='cyan', label='EMA 169'),
        mpf.make_addplot(df_plot['ema576'], color='magenta', label='EMA 576'),
        mpf.make_addplot(df_plot['ema676'], color='orange', label='EMA 676'),
    ]

    # Plotting signals as scatter plots on the chart
    buy_signals = np.where(df_plot['vegas_signal'] == 2, df_plot['Low'] * 0.99, np.nan)
    sell_signals = np.where(df_plot['vegas_signal'] == -2, df_plot['High'] * 1.01, np.nan)
    increase_signals = np.where(df_plot['wedge_signal'] == 1, df_plot['Low'] * 0.99, np.nan)
    decrease_signals = np.where(df_plot['wedge_signal'] == -1, df_plot['High'] * 1.01, np.nan)

    # Convert signal arrays to mplfinance addplot dictionaries, but only if they contain actual signals
    signal_plots = []

    # Check if buy signals exist (not all NaN)
    if not np.all(np.isnan(buy_signals)):
        signal_plots.append(mpf.make_addplot(buy_signals, type='scatter', markersize=100, marker='^', color='green',
                                             label='Buy Signal'))

    # Check if sell signals exist (not all NaN)
    if not np.all(np.isnan(sell_signals)):
        signal_plots.append(mpf.make_addplot(sell_signals, type='scatter', markersize=100, marker='v', color='red',
                                             label='Sell Signal'))

    # Check if increase signals exist (not all NaN)
    if not np.all(np.isnan(increase_signals)):
        signal_plots.append(mpf.make_addplot(increase_signals, type='scatter', markersize=100, marker='^', color='blue',
                                             label='Increase Signal'))

    # Check if decrease signals exist (not all NaN)
    if not np.all(np.isnan(decrease_signals)):
        signal_plots.append(
            mpf.make_addplot(decrease_signals, type='scatter', markersize=100, marker='v', color='orange',
                             label='Decrease Signal'))

    # Add signal plots to the list of additional plots only if we have any
    if signal_plots:
        apds.extend(signal_plots)

    # --- 2. Plotting the final chart ---
    mpf.plot(
        df_plot,
        type='candle',
        style='yahoo',
        title=title,
        ylabel='Price',
        addplot=apds,
        volume=True,
        figscale=1.5,
        figsize=(12, 8),
        tight_layout=True
    )


class VegasTunnelTestCase(TestCase):
    def setUp(self):
        make_db_connection()

    def test_update_signals(self):
        vt = VegasTunnel.get_instance()
        mds: MarketDataShovel = MarketDataShovel.get_instance()

        tickers = mds.get_latest_index_tickers('ndx').tickers

        full_bars: Dict[str, Dict[str, DataFrame]] = vt.update_signals(tickers=tickers, intervals=['30m', '65m'])

        for interval, ticker_bars in full_bars.items():
            for ticker, bars in ticker_bars.items():
                # Debug: Check if bars is empty and print info
                print(f"{interval} - {ticker}")
                print(f"Bars DataFrame shape: {bars.shape}")
                print(f"Bars DataFrame columns: {bars.columns.tolist()}")
                print(f"Bars DataFrame: {bars.head(6)}")
                if bars.empty:
                    print("Warning: Bars DataFrame is empty. Cannot plot.")
                    return
                plot_vegas_double_tunnel_signals(bars, ticker)

    def tearDown(self):
        disconnect_all()


if __name__ == '__main__':
    # Run the test manually
    test_case = VegasTunnelTestCase()
    test_case.setUp()
    try:
        test_case.test_update_signals()
    finally:
        test_case.tearDown()
