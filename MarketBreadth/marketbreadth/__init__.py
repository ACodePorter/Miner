from minerworkers import app

from ._market_breadth import MarketBreadth
from ._version import version

__all__ = ['MarketBreadth', 'version']

# app.autodiscover_tasks(['marketbreadth', 'dataminer'])
