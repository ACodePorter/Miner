from dataminer.tasks import us_task_chain, hk_task_chain
from marketbreadth.tasks import update_spx_market_breadth_task
from browserscraper.tasks import update_hk_market_pe_task
from celery import chain

us_daily_chain = us_task_chain | update_spx_market_breadth_task.si()

hk_daily_chain = hk_task_chain | update_hk_market_pe_task.si()
