from datetime import datetime, timedelta
from typing import Any, List, Optional

import pytz
from browserscraper.tasks import update_market_pe_task
from celery import chain
from dataminer import MarketDataShovel, WedgePop
from dataminer.models import MarketPe
from detonator import make_db_connection, mongo_2_df
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from marketbreadth import MarketBreadth
from marketbreadth.tasks import update_spx_market_breadth_task

from .tasks import (run_hk_daily_updates_task, run_us_daily_updates_task,
                    update_indicators_for_tickers_task,
                    update_iw_daily_ma_task,
                    update_iwd_tickers_daily_info_task,
                    update_iwd_tickers_info_task, update_iwd_tickers_task,
                    update_iwf_tickers_daily_info_task,
                    update_iwf_tickers_info_task, update_iwf_tickers_task,
                    update_iwm_tickers_daily_info_task,
                    update_iwm_tickers_info_task, update_iwm_tickers_task,
                    update_spx_daily_ma_task,
                    update_spx_tickers_daily_info_task,
                    update_spx_tickers_info_task, update_spx_tickers_task,
                    update_tickers_daily_info_task,
                    update_us_trade_calendar_task,
                    update_wedge_pop_for_index_task)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.get('/update_market_pe')
async def update_market_pe() -> str:
    update_market_pe_task.delay()
    return 'GOOD'


@app.get('/update_spx_market_breadth')
async def update_spx_market_breadth() -> str:
    update_spx_market_breadth_task.delay()
    return 'GOOD'


@app.get('/update_wedge_pop_for_index')
async def update_wedge_pop_for_index() -> str:
    update_wedge_pop_for_index_task.delay()
    return 'GOOD'


@app.get('/run_us_daily_updates', description='Update US daily data')
async def run_us_daily_updates() -> str:
    run_us_daily_updates_task.delay()
    return 'GOOD'


@app.get('/run_hk_daily_updates')
async def update_hk_daily_updates() -> str:
    run_hk_daily_updates_task.delay()
    return 'GOOD'


@app.post('/update_indicators_for_tickers')
async def update_indicators_for_tickers(tickers: List[str]) -> str:
    update_indicators_for_tickers_task.delay(tickers=tickers)
    return 'GOOD'


@app.get('/api/mbs/{market_index}.json')
async def get_mbs(market_index: str = 'spx', start_date: str = None, end_date: str = None) -> list | dict:
    '''
    获取市场宽度分数
    :return:
    '''
    make_db_connection()
    return MarketBreadth.get_instance().get_market_breath(market_index=market_index, start_date=start_date,
                                                          end_date=end_date).to_dict(orient='records')


@app.get('/api/market_pe/{index}.json')
async def get_market_pe(index: str = 'spx', start_date: str = None, end_date: str = None) -> dict:
    '''
    Get market PE data for visualization
    :param index: 'spx' or 'qqq'
    :param start_date: start date in YYYY-MM-DD format (optional)
    :param end_date: end date in YYYY-MM-DD format (optional)
    :return: dict with PE data and statistics
    '''
    make_db_connection()

    # Set default date range if not provided
    if not end_date:
        end_date = datetime.now(tz=pytz.timezone(
            'America/New_York')).strftime('%Y-%m-%d')
    if not start_date:
        # Default to 20 years ago
        start_date = (datetime.now(tz=pytz.timezone('America/New_York')
                                   ) - timedelta(days=365*20)).strftime('%Y-%m-%d')

    # Convert dates to datetime objects for querying
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')

    # Query the database
    query = {
        'idx': index,
        'trade_date__gte': start_dt,
        'trade_date__lte': end_dt
    }

    df = mongo_2_df(MarketPe.objects(**query).order_by('trade_date'))

    if df.empty:
        return {
            'index': index,
            'data': [],
            'stats': {
                'avg_20y': 0,
                'current_pe': 0,
                'min_pe': 0,
                'max_pe': 0
            }
        }

    # Convert to Highcharts format [timestamp, pe_value]
    data = []
    for _, row in df.iterrows():
        # Handle trade_date which might be a string from mongo_2_df
        if isinstance(row['trade_date'], str):
            # Parse the string date format from MongoDB
            # The scraper stores dates in format "2024,01,15,00,00,00,000000"
            try:
                # Try to parse the custom format used by the scraper
                dt = datetime.strptime(
                    row['trade_date'], '%Y,%m,%d,%H,%M,%S,%f')
            except ValueError:
                try:
                    # Try to parse ISO format as fallback
                    dt = datetime.fromisoformat(
                        row['trade_date'].replace('Z', '+00:00'))
                except ValueError:
                    # Fallback to other common formats
                    dt = datetime.strptime(
                        row['trade_date'], '%Y-%m-%d %H:%M:%S')
        else:
            # If it's already a datetime object
            dt = row['trade_date']

        timestamp = int(dt.timestamp() * 1000)  # Convert to milliseconds
        data.append([timestamp, float(row['pe'])])

    # Calculate statistics
    pe_values = df['pe'].values
    avg_20y = float(pe_values.mean())
    current_pe = float(pe_values[-1]) if len(pe_values) > 0 else 0
    min_pe = float(pe_values.min())
    max_pe = float(pe_values.max())

    return {
        'index': index,
        'data': data,
        'stats': {
            'avg_20y': avg_20y,
            'current_pe': current_pe,
            'min_pe': min_pe,
            'max_pe': max_pe
        }
    }


@app.get('/api/wedge_pop/latest.json', description='Get all wedge pop tickers of today')
async def get_wedge_pop_tickers_of_today() -> dict | list:
    wedge_pop: WedgePop = WedgePop.get_instance()
    return wedge_pop.get_wedge_tickers_on_today()


@app.get('/api/wedge_pop/wedges.json', description='Get wedge pop tickers since 1 year ago')
async def get_wedge_pop_tickers() -> dict | list:
    wedge_pop: WedgePop = WedgePop.get_instance()
    start_date = datetime.now(tz=pytz.timezone(
        'America/New_York')) - timedelta(days=365)
    return wedge_pop.get_wedge_tickers_since(start_date)


@app.get('/api/wedge_pop/stats.json', description='Get wedge pop stats')
async def get_wedge_pop_stats(start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict | list:
    wedge_pop: WedgePop = WedgePop.get_instance()
    return wedge_pop.get_wedge_stats(start_date=start_date, end_date=end_date)


@app.get('/api/ohlcvw/{ticker}.json', description='Get OHLCVW data for a ticker, default to 3 years ago')
async def get_ohlcvw(ticker: str, start_date: Optional[str] = None, end_date: Optional[str] = None, interval: str = '1d') -> dict | list[Any]:
    md: MarketDataShovel = MarketDataShovel.get_instance()
    if start_date is None:
        start_date = datetime.now(tz=pytz.timezone(
            'America/New_York')) - timedelta(days=365*3)
    if end_date is None:
        end_date = datetime.now(tz=pytz.timezone(
            'America/New_York'))
    dailies_df = md.get_ticker_daily_info(
        ticker, start_date, end_date, interval=interval)
    dailies_df = dailies_df[['trade_date', 'ticker', 'open',
                             'high', 'low', 'close', 'volume', 'wedge_status']]
    return dailies_df.to_dict(orient='records')
