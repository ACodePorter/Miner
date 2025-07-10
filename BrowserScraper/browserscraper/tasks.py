from minerworkers import app
from ._market_valuation_scraper import MarketValuationScraper

@app.task
def update_market_pe_task() -> bool:
    """
    Task to update the market P/E ratio using the MarketValuationScraper.
    This task is registered with Celery and can be scheduled or called directly.
    """
    scraper = MarketValuationScraper.get_instance()
    return scraper.update_idx_pe_to_latest('spx') & scraper.update_idx_pe_to_latest('qqq')
