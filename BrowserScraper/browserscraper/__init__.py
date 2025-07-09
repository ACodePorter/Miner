from minerworkers import app
from ._version import __version__
from ._market_valuation_scraper import MarketValuationScraper

__all__ = [
    '__version__',
    'MarketValuationScraper'
]

app.autodiscover_tasks(['browserscraper'], force=True)
