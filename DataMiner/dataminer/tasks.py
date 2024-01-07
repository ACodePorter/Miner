from typing import List

from detonator import get_logger
from minerworkers import app

from . import MarketDataShovel
from ._ishares_shovel import IsharesShovel
from ._trade_cal import TradeCalendarShovel

_logger = get_logger('DataMiner.Tasks')


@app.task
def update_russell1000_tickers_task() -> bool:
    shovel: IsharesShovel = IsharesShovel.get_instance()
    return shovel.update_russell1000_tickers_from_ishare_2_db()


@app.task
def update_spx_tickers_task() -> bool:
    _logger.debug('update_spx_tickers_task')
    mds: MarketDataShovel = MarketDataShovel.get_instance()
    return mds.update_spx_tickers()


@app.task
def update_spx_tickers_info_task() -> bool:
    _logger.debug('update_spx_tickers_info_task')
    mds: MarketDataShovel = MarketDataShovel.get_instance()
    return mds.update_spx_tickers_info()


@app.task
def update_spx_tickers_daily_info_task() -> bool:
    _logger.debug('update_spx_tickers_daily_info')
    mds: MarketDataShovel = MarketDataShovel.get_instance()
    return mds.update_spx_tickers_daily_info()


@app.task
def update_us_trade_calendar_task() -> bool:
    _logger.debug('update_us_trade_calendar_task')
    tcs: TradeCalendarShovel = TradeCalendarShovel.get_instance()
    tcs.update_us_trade_calendar()
    return True


@app.task
def update_tickers_daily_info_task(tickers: List[str]) -> bool:
    _logger.debug('update_us_trade_calendar_task')
    mds: MarketDataShovel = MarketDataShovel.get_instance()
    return mds.update_tickers_daily_info(tickers)
