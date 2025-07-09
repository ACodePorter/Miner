from minerworkers import app

@app.task
def update_market_pe_task() -> bool:
    return True
