from typing import List

from browserscraper.tasks import update_hk_market_pe_task
from celery import chain
from dataminer import (Indicators, IsharesScraper, MarketDataShovel,
                       TradeCalendarShovel, WedgePop)
from detonator import get_logger
from marketbreadth.tasks import update_spx_market_breadth_task
from minerworkers import app

_logger = get_logger('MinerService.Tasks')


@app.task
def update_russell1000_tickers_task() -> bool:
    shovel: IsharesScraper = IsharesScraper.get_instance()
    return shovel.update_russell1000_tickers_from_ishare_2_db()


@app.task
def update_spx_tickers_task() -> bool:
    _logger.debug('update_spx_tickers_task')
    mds: MarketDataShovel = MarketDataShovel.get_instance()
    return mds.update_spx_tickers()


@app.task
def update_ndx_tickers_task() -> bool:
    _logger.debug('update_ndx_tickers_task')
    mds: MarketDataShovel = MarketDataShovel.get_instance()
    return mds.update_ndx_tickers()


@app.task
def update_iwd_tickers_task() -> bool:
    _logger.debug('update_iwd_tickers_task')
    mds: MarketDataShovel = MarketDataShovel.get_instance()
    return mds.update_iwd_tickers()


@app.task
def update_iwf_tickers_task() -> bool:
    _logger.debug('update_iwf_tickers_task')
    mds: MarketDataShovel = MarketDataShovel.get_instance()
    return mds.update_iwf_tickers()


@app.task
def update_iwm_tickers_task() -> bool:
    _logger.debug('update_iwm_tickers_task')
    mds: MarketDataShovel = MarketDataShovel.get_instance()
    return mds.update_iwm_tickers()


@app.task
def update_spx_tickers_info_task() -> bool:
    _logger.debug('update_spx_tickers_info_task')
    mds: MarketDataShovel = MarketDataShovel.get_instance()
    return mds.update_spx_tickers_info()


@app.task
def update_ndx_tickers_info_task() -> bool:
    _logger.debug('update_ndx_tickers_info_task')
    mds: MarketDataShovel = MarketDataShovel.get_instance()
    return mds.update_ndx_tickers_info()


@app.task
def update_iwd_tickers_info_task() -> bool:
    _logger.debug('update_iwd_tickers_info_task')
    mds: MarketDataShovel = MarketDataShovel.get_instance()
    return mds.update_iwd_tickers_info()


@app.task
def update_iwf_tickers_info_task() -> bool:
    _logger.debug('update_iwf_tickers_info_task')
    mds: MarketDataShovel = MarketDataShovel.get_instance()
    return mds.update_iwf_tickers_info()


@app.task
def update_iwm_tickers_info_task() -> bool:
    _logger.debug('update_iwm_tickers_info_task')
    mds: MarketDataShovel = MarketDataShovel.get_instance()
    return mds.update_iwm_tickers_info()


@app.task
def update_tickers_info_task(tickers: List[str]) -> bool:
    _logger.debug('update_tickers_info_task')
    mds: MarketDataShovel = MarketDataShovel.get_instance()
    return mds.update_tickers_info(tickers)


@app.task
def update_spx_tickers_daily_info_task() -> bool:
    _logger.debug('update_spx_tickers_daily_info')
    mds: MarketDataShovel = MarketDataShovel.get_instance()
    return mds.update_spx_tickers_daily_info()


@app.task
def update_ndx_tickers_daily_info_task() -> bool:
    _logger.debug('update_ndx_tickers_daily_info')
    mds: MarketDataShovel = MarketDataShovel.get_instance()
    return mds.update_ndx_tickers_daily_info()


@app.task
def update_iwd_tickers_daily_info_task() -> bool:
    _logger.debug('update_iwd_tickers_daily_info')
    mds: MarketDataShovel = MarketDataShovel.get_instance()
    return mds.update_iwd_tickers_daily_info()


@app.task
def update_iwf_tickers_daily_info_task() -> bool:
    _logger.debug('update_iwf_tickers_daily_info')
    mds: MarketDataShovel = MarketDataShovel.get_instance()
    return mds.update_iwf_tickers_daily_info()


@app.task
def update_iwm_tickers_daily_info_task() -> bool:
    _logger.debug('update_iwm_tickers_daily_info')
    mds: MarketDataShovel = MarketDataShovel.get_instance()
    return mds.update_iwm_tickers_daily_info()


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
    return not mds.update_tickers_daily_info(tickers)


@app.task
def update_us_idxs_daily_info_task() -> bool:
    _logger.debug('update_us_idxs_daily_info_task')
    mds: MarketDataShovel = MarketDataShovel.get_instance()
    return mds.update_ticker_daily_info('^SPX') & mds.update_ticker_daily_info('^NDX') & mds.update_ticker_daily_info(
        '^RUT')


@app.task
def update_spx_daily_ma_task() -> bool:
    _logger.debug('update_spx_daily_sma_task')
    indicators: Indicators = Indicators.get_instance()
    return indicators.update_spx_daily_ma()


@app.task
def update_iw_daily_ma_task() -> bool:
    _logger.debug('update_iw_daily_ma_task')
    indicators: Indicators = Indicators.get_instance()
    indicators.update_daily_ma_by_idx('iwd')
    indicators.update_daily_ma_by_idx('iwf')
    indicators.update_daily_ma_by_idx('iwm')
    return True


@app.task
def update_indicators_for_tickers_task(tickers: List[str]) -> bool:
    _logger.debug('update_indicators_for_tickers_task')
    indicators: Indicators = Indicators.get_instance()
    return indicators.update_indicators_for_tickers(tickers)


@app.task
def update_wedge_pop_for_index_task() -> bool:
    _logger.debug('update_wedge_pop_for_index_task')
    wedge_pop: WedgePop = WedgePop.get_instance()
    return all([wedge_pop.update_wedge_pop_for_index('spx'),
                wedge_pop.update_wedge_pop_for_index('iwd'),
                wedge_pop.update_wedge_pop_for_index('iwf'),
                wedge_pop.update_wedge_pop_for_index('iwm')])


@app.task
def update_ndx_intraday_bars_task() -> bool:
    _logger.debug('update_ndx_intraday_bars_task')
    mds: MarketDataShovel = MarketDataShovel.get_instance()
    return mds.update_intraday_bars_by_idx('ndx')


@app.task
def run_us_daily_updates_task() -> bool:
    """
    Run all daily update tasks in sequence at 16:30 (with 5 min window)
    The sequence is:
    1. Update trade calendar
    2. Update all ticker lists and their info
    3. Update daily info for all tickers
    4. Update indicators and market breadth
    """
    _logger.info('Starting daily updates sequence')

    # Create the task chain
    task_chain = chain(
        # First update trade calendar
        update_us_trade_calendar_task.si(),

        update_ndx_tickers_task.si(),
        update_ndx_tickers_info_task.si(),
        update_ndx_tickers_daily_info_task.si(),
        update_ndx_intraday_bars_task.task.si(),

        # Then update all ticker lists and their info
        update_spx_tickers_task.si(),
        update_spx_tickers_info_task.si(),
        update_spx_tickers_daily_info_task.si(),
        update_spx_daily_ma_task.si(),
        # update market breadth
        update_spx_market_breadth_task.si(),

        update_iwd_tickers_task.si(),
        update_iwd_tickers_info_task.si(),
        update_iwd_tickers_daily_info_task.si(),

        update_iwf_tickers_task.si(),
        update_iwf_tickers_info_task.si(),
        update_iwf_tickers_daily_info_task.si(),

        update_iwm_tickers_task.si(),
        update_iwm_tickers_info_task.si(),
        update_iwm_tickers_daily_info_task.si(),

        # Then update daily info for all tickers
        update_iw_daily_ma_task.si(),

        # update wedge pop/drop for all tickers
        update_wedge_pop_for_index_task.si(),

        # Then update idxs daily info
        update_us_idxs_daily_info_task.si(),

    )

    # Execute the chain
    task_chain.apply_async()
    return True


@app.task
def update_hk_idxs_daily_info_task() -> bool:
    _logger.debug('update_hk_idxs_daily_info_task')
    mds: MarketDataShovel = MarketDataShovel.get_instance()
    return mds.update_ticker_daily_info('^HSI')


@app.task
def update_hk_trade_calendar_task() -> bool:
    _logger.debug('update_hk_trade_calendar_info_task')
    tcs: TradeCalendarShovel = TradeCalendarShovel.get_instance()
    return tcs.update_hk_trade_calendar()


@app.task
def run_hk_daily_updates_task() -> bool:
    _logger.debug('run_hk_daily_updates_task')
    task_chain = chain(
        update_hk_trade_calendar_task.si(),
        update_hk_idxs_daily_info_task.si(),
        update_hk_market_pe_task.si(),
    )
    task_chain.apply_async()
    return True
