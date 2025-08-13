import time

from dataminer._ws_thread import LiveQuoteSource


class ExampleWsThread():
    def __init__(self):
        self.ws = LiveQuoteSource(self.handle_quote)
        self.ws.start()

    def handle_quote(self, quote: dict):
        print(quote)

    def subscribe(self, tickers: list[str]):
        self.ws.subscribe(tickers)

    def unsubscribe(self, tickers: list[str]):
        self.ws.unsubscribe(tickers)

    def stop(self):
        self.ws.join()


if __name__ == "__main__":
    ws = ExampleWsThread()
    ws.subscribe(["AAPL", "TSLA", "MSFT"])
    time.sleep(10)
    ws.unsubscribe(["AAPL", "MSFT"])
    time.sleep(10)

    ws.stop()
