from fastapi import FastAPI
from dataminer.tasks import update_spx_tickers_task, update_spx_tickers_info_task
from celery import chain

app = FastAPI()


@app.get('/')
async def root():
    return {'Hello': 'World'}


@app.get('/update_spx_tickers_info')
async def update_spx_tickers_info() -> str:
    chain(update_spx_tickers_task.si(), update_spx_tickers_info_task.si())()
    return 'Good'
