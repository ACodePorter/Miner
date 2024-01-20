from minerworkers import app

from . import MarketBreadth


@app.task
def update_spx_market_breadth_task() -> bool:
    mb: MarketBreadth = MarketBreadth.get_instance()
    return mb.update_index_breadth('spx')
