"""Watchlist management endpoints"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Query

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get('')
async def get_watchlist() -> Dict[str, Any]:
    """Get the current watchlist"""
    try:
        # For now, we'll use a simple file-based storage
        # In production, you might want to use a database
        watchlist_file = 'watchlist.json'
        if os.path.exists(watchlist_file):
            with open(watchlist_file, 'r') as f:
                watchlist: List[Dict[str, Any]] = json.load(f)
        else:
            watchlist: List[Dict[str, Any]] = []
        return {'watchlist': watchlist}
    except Exception as e:
        return {'error': str(e), 'watchlist': []}


@router.post('')
async def add_to_watchlist(ticker: str = Query(..., description="Ticker symbol to add to watchlist")) -> Dict[str, Any]:
    """Add a ticker to the watchlist"""
    try:
        watchlist_file = 'watchlist.json'
        watchlist: List[Dict[str, Any]] = []

        if os.path.exists(watchlist_file):
            with open(watchlist_file, 'r') as f:
                watchlist = json.load(f)

        # Check if ticker already exists
        if ticker.upper() not in [item['ticker'] for item in watchlist]:
            watchlist.append({
                'ticker': ticker.upper(),
                'added_at': datetime.now().isoformat()
            })

            with open(watchlist_file, 'w') as f:
                json.dump(watchlist, f, indent=2)

            return {'status': 'success', 'message': f'{ticker.upper()} added to watchlist'}
        else:
            return {'status': 'error', 'message': f'{ticker.upper()} already in watchlist'}

    except Exception as e:
        return {'status': 'error', 'message': str(e)}


@router.delete('/{ticker}')
async def remove_from_watchlist(ticker: str) -> Dict[str, Any]:
    """Remove a ticker from the watchlist"""
    try:
        watchlist_file = 'watchlist.json'
        if not os.path.exists(watchlist_file):
            return {'status': 'error', 'message': 'Watchlist not found'}

        with open(watchlist_file, 'r') as f:
            watchlist: List[Dict[str, Any]] = json.load(f)

        # Remove the ticker
        original_length = len(watchlist)
        watchlist = [
            item for item in watchlist if item['ticker'] != ticker.upper()]

        if len(watchlist) < original_length:
            with open(watchlist_file, 'w') as f:
                json.dump(watchlist, f, indent=2)
            return {'status': 'success', 'message': f'{ticker.upper()} removed from watchlist'}
        else:
            return {'status': 'error', 'message': f'{ticker.upper()} not found in watchlist'}

    except Exception as e:
        return {'status': 'error', 'message': str(e)}
