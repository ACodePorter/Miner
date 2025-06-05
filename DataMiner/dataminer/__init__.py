import os

import tushare as ts
# from minerworkers import app
from detonator import get_logger

from ._financial_shovel import FinancialShovel
from ._indicators import Indicators
from ._ishares_scraper import IsharesScraper
from ._market_data_shovel import MarketDataShovel
from ._ticker_manager import TickerManager
from ._trade_cal import TradeCalendarShovel
from ._version import version
from .models import Ticker, Balancesheet, CashflowTable, Financials, TradeCalendar

__all__ = [
    'version',
    'Indicators',
    'IsharesScraper',
    'FinancialShovel',
    'MarketDataShovel',
    'Ticker',
    'Balancesheet', 'CashflowTable', 'Financials', 'TradeCalendar',
    'TickerManager',
    'TradeCalendarShovel'
]

if 'TUSHARE_KEY' in os.environ:
    ts.set_token(os.environ['TUSHARE_KEY'])
else:
    get_logger('DataMiner').warning('TUSHARE_KEY not available')
    get_logger('DataMiner').warning('TUSHARE_KEY not available')
    get_logger('DataMiner').warning('TUSHARE_KEY not available')
    get_logger('DataMiner').warning('TUSHARE_KEY not available')
    get_logger('DataMiner').warning('TUSHARE_KEY not available')
    get_logger('DataMiner').warning('TUSHARE_KEY not available')
    get_logger('DataMiner').warning('TUSHARE_KEY not available')


# app.autodiscover_tasks(['dataminer'])
