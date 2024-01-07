from typing import List

from celery import chain
from dataminer.tasks import update_spx_tickers_task, update_spx_tickers_info_task, update_spx_tickers_daily_info_task, \
    update_us_trade_calendar_task, update_tickers_daily_info_task
from fastapi import FastAPI

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


@app.get('/update_spx_tickers_daily_info')
async def update_spx_tickers_daily_info() -> str:
    update_spx_tickers_daily_info_task.delay()
    return 'GOOD'


@app.post('/update_tickers_daily_info')
async def update_tickers_daily_info(tickers: List[str]) -> str:
    update_tickers_daily_info_task.delay(tickers=tickers)
    return 'GOOD'
