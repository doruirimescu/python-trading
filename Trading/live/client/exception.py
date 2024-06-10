from Trading.utils.time import get_datetime_now_cet
class MarketClosedException(Exception):
    def __init__(self, symbol: str):
        current_time = get_datetime_now_cet()
        super().__init__(f"Market is closed for symbol: {symbol} at {current_time}")
class ServerNotUpException(Exception):
    def __init__(self):
        super().__init__("Server is not up")
