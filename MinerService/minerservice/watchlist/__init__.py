from .model import Watchlist, Bar
from typing import Dict, Any

async def add_bars_to_watchlist(user_id: str, ticker: str, interval: str):
    watchlist = Watchlist.objects(user_id=user_id).first()
    if not watchlist:
        watchlist = Watchlist(user_id=user_id)
    watchlist.bars.append(Bar(ticker=ticker, interval=interval))
    watchlist.save()

async def get_all_watchlist(user_id: str) -> Dict[str, Any]:
    watchlist = Watchlist.objects(user_id=user_id).first()
    if not watchlist:
        return {}
    return watchlist.as_dict()




__all__ = ['add_bars_to_watchlist', 'get_all_watchlist']

