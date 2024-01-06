import os

import tushare as ts
from minerworkers import app

from ._financial_shovel import FinancialShovel
from ._ishares_shovel import IsharesShovel
from ._market_data_shovel import MarketDataShovel
from ._ticker_manager import TickerManager
from ._trade_cal import TradeCalendarShovel
from ._version import version
from .models import Ticker, Balancesheet, CashflowTable, Financials, TradeCalendar

__all__ = [
    'version',
    'IsharesShovel',
    'FinancialShovel',
    'MarketDataShovel',
    'Ticker',
    'Balancesheet', 'CashflowTable', 'Financials', 'TradeCalendar',
    'TickerManager',
    'TradeCalendarShovel'
]

ts.set_token(os.environ['TUSHARE_KEY'])

app.autodiscover_tasks(['dataminer'])
