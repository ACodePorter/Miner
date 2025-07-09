from typing import List

from celery import chain
from dataminer.tasks import update_iwm_tickers_info_task, update_iwd_tickers_task, update_iwd_tickers_info_task, \
    update_iwd_tickers_daily_info_task, update_iwf_tickers_daily_info_task, update_iwm_tickers_daily_info_task
from dataminer.tasks import update_spx_tickers_task, update_iwf_tickers_task, \
    update_spx_tickers_info_task, update_spx_tickers_daily_info_task, \
    update_us_trade_calendar_task, update_tickers_daily_info_task, update_spx_daily_ma_task, update_iwm_tickers_task, \
    update_iwf_tickers_info_task, update_indicators_for_tickers_task, run_daily_updates_task, update_iw_daily_ma_task
from detonator import make_db_connection
from fastapi import FastAPI
from marketbreadth import MarketBreadth
from marketbreadth.tasks import update_spx_market_breadth_task

app = FastAPI()


@app.get('/')
async def root():
    return {'Hello': 'World'}


@app.get('/update_us_trade_calendar')
async def update_us_trade_calendar() -> str:
    update_us_trade_calendar_task.delay()
    return 'GOOD'


@app.get('/update_spx_tickers_info')
async def update_spx_tickers_info() -> str:
    chain(update_spx_tickers_task.si(), update_spx_tickers_info_task.si())()
    return 'GOOD'


@app.get('/update_iwd_tickers_info')
async def update_iwf_tickers_info() -> str:
    chain(update_iwd_tickers_task.si(), update_iwd_tickers_info_task.si())()
    return 'GOOD'


@app.get('/update_iwf_tickers_info')
async def update_iwf_tickers_info() -> str:
    chain(update_iwf_tickers_task.si(), update_iwf_tickers_info_task.si())()
    return 'GOOD'


@app.get('/update_iwm_tickers_info')
async def update_iwm_tickers_info() -> str:
    chain(update_iwm_tickers_task.si(), update_iwm_tickers_info_task.si())()
    return 'GOOD'


@app.get('/update_spx_tickers_daily_info')
async def update_spx_tickers_daily_info() -> str:
    update_spx_tickers_daily_info_task.delay()
    return 'GOOD'


@app.get('/update_iwd_tickers_daily_info')
async def update_iwd_tickers_daily_info() -> str:
    update_iwd_tickers_daily_info_task.delay()
    return 'GOOD'


@app.get('/update_iwf_tickers_daily_info')
async def update_iwf_tickers_daily_info() -> str:
    update_iwf_tickers_daily_info_task.delay()
    return 'GOOD'


@app.get('/update_iwm_tickers_daily_info')
async def update_iwm_tickers_daily_info() -> str:
    update_iwm_tickers_daily_info_task.delay()
    return 'GOOD'


@app.post('/update_tickers_daily_info')
async def update_tickers_daily_info(tickers: List[str]) -> str:
    update_tickers_daily_info_task.delay(tickers=tickers)
    return 'GOOD'


@app.get('/update_spx_daily_ma')
async def update_spx_daily_ma() -> str:
    update_spx_daily_ma_task.delay()
    return 'GOOD'


@app.get('/update_iw_daily_ma')
async def update_iw_daily_ma() -> str:
    update_iw_daily_ma_task.delay()
    return 'GOOD'


@app.get('/update_all_above', description='Update all above tasks to fetch latest data')
async def update_all_above() -> str:
    run_daily_updates_task.delay()
    return 'GOOD'


@app.post('/update_indicators_for_tickers')
async def update_indicators_for_tickers(tickers: List[str]) -> str:
    update_indicators_for_tickers_task.delay(tickers=tickers)
    return 'GOOD'


@app.get('/update_spx_market_breadth')
async def update_spx_market_breadth() -> str:
    update_spx_market_breadth_task.delay()
    return 'GOOD'


@app.get('/mbs')
async def get_mbs(market_index: str = 'spx', start_date: str = None, end_date: str = None) -> list | dict:
    '''
    获取市场宽度分数
    :return:
    '''
    make_db_connection()
    return MarketBreadth.get_instance().get_market_breath(market_index=market_index, start_date=start_date,
                                                          end_date=end_date).to_dict(orient='records')
