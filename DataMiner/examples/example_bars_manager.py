import time

from dataminer import BarsManager

if __name__ == "__main__":
    bm = BarsManager.get_instance()
    bm.subscribe("AAPL")
    time.sleep(5)
    bm.unsubscribe("AAPL")
    bm.subscribe(["GOOG", "NVDA"])
    time.sleep(5)
    print("restarting live quotes")
    print("restarting live quotes")
    print("restarting live quotes")
    print("restarting live quotes")
    print("restarting live quotes")
    print("restarting live quotes")
    bm.restart_live_quotes()
    time.sleep(5)
    bm.stop_live_quotes()
