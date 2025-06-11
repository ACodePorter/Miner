import time
import traceback
from threading import Lock

import requests
from detonator import get_logger, SingletonParent

_logger = get_logger('TickerRegulator')


class TickerRegulator(SingletonParent):
    def __init__(self, cache_expiry_hours=2):
        self.cache_expiry = cache_expiry_hours * 3600  # seconds
        self._tickers = set()
        self._last_updated = 0
        self._lock = Lock()

    def validate_ticker(self, ticker: str = '') -> str:
        """
        valid if the ticker is in the SEC's official list of tickers.
        if possible return the ticker or empty str if not valid.
        """
        if not ticker:
            _logger.exception('Invalid ticker: Empty')
            return ''
        with self._lock:
            now = time.time()
            if now - self._last_updated > self.cache_expiry or not self._tickers:
                self._refresh_cache()
            if ticker.upper() in self._tickers:
                return ticker.upper()
            t = (ticker[:-1] + '-' + ticker[-1]).upper()
            return t if t in self._tickers else ''

    def _refresh_cache(self):
        try:
            headers = {
                'User-Agent': 'YourAppName/1.0 (your.email@example.com)'
            }
            url = "https://www.sec.gov/files/company_tickers.json"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            self._tickers = {entry['ticker'].upper() for entry in data.values()}
            self._last_updated = time.time()
            _logger.info('Refreshed tickers')
        except Exception as e:
            _logger.error(f"Failed to refresh ticker cache", exc_info=e)
            self._tickers = set()

