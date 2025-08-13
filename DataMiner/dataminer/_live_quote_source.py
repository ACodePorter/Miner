from threading import Thread
from typing import Any, Callable, Dict

from detonator import get_logger
from yfinance import WebSocket


class LiveQuoteSource(Thread):
    def __init__(self, handle_quote: Callable[[Dict[str, Any]], None], on_error: Callable[[Exception], None] = None):
        super().__init__()
        self.handle_quote = handle_quote
        self.ws = WebSocket(verbose=False)
        self.logger = get_logger(__name__)
        self.on_error = on_error
        self.subscribed_tickers = set()
        self.closed = False

    def run(self):
        try:
            self.closed = False
            self.logger.info("Starting WebSocket listener")
            self.ws.subscribe(list(self.subscribed_tickers))
            self.ws.listen(self.handle_quote)
        except Exception as e:
            if self.on_error is not None and not self.closed:
                self.logger.error(
                    "Error listening to WebSocket: %s", e)
                self.on_error(e)
        finally:
            try:
                if self.ws is not None:
                    self.ws.close()
                    self.ws = None
            except Exception as e:
                self.logger.error("Error closing WebSocket: %s", e)

    def stop(self) -> None:
        if self.ws is not None:
            self.closed = True
            self.ws.close()
            self.ws = None
        return super().join(60)

    def subscribe(self, tickers: list[str]) -> None:
        if isinstance(tickers, str):
            tickers = [tickers]
        tickers = [t.upper().replace('.', '-') for t in tickers]
        self.subscribed_tickers.update(tickers)
        if self.is_alive():
            self.ws.subscribe(tickers)
        else:
            self.start()

    def unsubscribe(self, tickers: list[str]) -> None:
        if isinstance(tickers, str):
            tickers = [tickers]
        tickers = [t.upper().replace('.', '-') for t in tickers]
        self.subscribed_tickers.difference_update(tickers)
        if self.ws is not None:
            self.ws.unsubscribe(tickers)
