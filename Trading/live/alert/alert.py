from Trading.live.client.client import LoggingClient, TradingClient
from Trading.instrument.timeframes import TIMEFRAMES_TO_NAME
from Trading.instrument import Instrument, Timeframe
from Trading.utils.calculations import round_to_two_decimals
from datetime import datetime
from typing import Optional, Tuple, List
from pydantic import BaseModel


def get_top_ten_biggest_swaps_report(client: LoggingClient) -> Tuple[str, List]:
    biggest_swaps = client.get_top_ten_biggest_swaps()
    report = "Top 10 biggest swaps:\n\n"
    report += "|{:^15}|{:^15}|{:^15}|\n".format("Pair", "Swap Long", "Swap Short")
    report += "-------------------------------------------------\n"
    for sym, sl, ss in biggest_swaps:
        report += f"|{sym:^15}|{sl:^15}|{ss:^15}|"
        report += "\n"
    print(report)
    return report, biggest_swaps


def get_total_swap_of_open_forex_trades_report(client: TradingClient) -> Tuple[str, List]:
    open_trade_swaps = client.get_swaps_of_forex_open_trades()
    print(open_trade_swaps)
    report = ""
    for symbol, swap in open_trade_swaps:
        if swap < 0.0:
            date_now = str(datetime.now().date())
            report + f"Open trade swap gone negative, symbol: {symbol} swap: {str(swap)} date:{date_now}\n"

    total_profit, total_swap, text_message, data = client.get_total_forex_open_trades_profit_and_swap()
    report += text_message
    report += f"\nTotal profit: {str(total_profit)} Total swap: {str(round_to_two_decimals(total_swap))}\n"
    biggest_swaps = client.get_top_ten_biggest_swaps()
    report += f"\nBiggest 10 swaps:\n"
    for sym, sl, ss in biggest_swaps[0:10]:
        report += "Pair:\t{}\tSwap long:{:>10}\tSwap short:{:>10}\n".format(
                            sym, sl, ss)
    return report, data



def is_symbol_price_below_last_n_intervals_low(client: LoggingClient,
                                               instrument: Instrument,
                                               n: int) -> Optional[str]:
    info = client.get_symbol(instrument.symbol)
    price = float(info['ask'])
    history = client.get_last_n_candles_history(instrument, n)['low'][:-1]
    minimum = min(history)
    if price < minimum:
        return (
            f"{instrument.symbol} price {price} has gone "
            f"below the past {n} {TIMEFRAMES_TO_NAME[instrument.timeframe]} timeframe low {minimum}"
        )
    return None


def is_symbol_price_above_last_n_intervals_low(client: LoggingClient,
                                               instrument: Instrument,
                                               n: int) -> Optional[str]:
    info = client.get_symbol(instrument.symbol)
    price = float(info['bid'])
    history = client.get_last_n_candles_history(instrument, n)['high'][:-1]
    maximum = max(history)
    if price > maximum:
        return (
            f"{instrument.symbol} price {price} has gone "
            f"above the past {n} {TIMEFRAMES_TO_NAME[instrument.timeframe]} timeframe high {maximum}"
        )
    return None

from enum import Enum
from typing import Callable, Optional
from Trading.instrument.price import BidAsk
from Trading.utils.send_email import send_email
from abc import abstractmethod
import operator

# Dictionary mapping operator functions to their string representations
operator_strings = {
    operator.lt: "<",
    operator.le: "<=",
    operator.eq: "==",
    operator.ne: "!=",
    operator.ge: ">=",
    operator.gt: ">",
    operator.add: "+",
    operator.sub: "-",
    operator.mul: "*",
    operator.truediv: "/",
    operator.floordiv: "//",
    operator.mod: "%",
    operator.pow: "**",
    operator.and_: "&",
    operator.or_: "|",
    operator.xor: "^",
    operator.not_: "not",
    operator.inv: "~"
}
class AlertAction(Enum):
    SEND_EMAIL = 0
    PRINT_MESSAGE = 1
    RING_BELL = 2

# Schedule should not be used in this class, it should be used in the runner (github action)
class Alert(BaseModel):
    name: str
    description: str
    schedule: str
    type: str
    data_source: str
    operator: Callable
    threshold_value: float
    action: Optional[AlertAction] = None
    message: Optional[str] = None
    is_handled: bool = False
    is_triggered: bool = False

    @abstractmethod
    def are_conditions_valid(self, *args, **kwargs) -> bool:
        # Check if the conditions for the alert are met
        ...

    @abstractmethod
    def _should_trigger(self, *args, **kwargs) -> bool:
        ...

    def evaluate(self, *args, **kwargs):
        if not self._should_trigger(*args, **kwargs) or self.is_handled:
            return
        if self.action == AlertAction.SEND_EMAIL:
            send_email(subject=self.name, body=self.message)
        elif self.action == AlertAction.PRINT_MESSAGE:
            from Trading.utils.custom_logging import get_logger
            logger = get_logger("AlertLogger")
            logger.info(self.message)
        elif self.action == AlertAction.RING_BELL:
            pass


class XTBSpotAlert(Alert):
    symbol: str
    bid_ask: BidAsk

    def are_conditions_valid(self, client: LoggingClient) -> bool:
        is_market_open = client.is_market_open(self.symbol)
        return is_market_open

    def _trigger(self, bid_ask: str, price: float):
        self.is_triggered = True
        self.message = (f"{self.symbol} {bid_ask} price of {price} is {operator_strings[self.operator]} "
                        f"{self.threshold_value} from datasource: {self.data_source}")

    def _untrigger(self):
        self.is_triggered = False
        self.is_handled = False
        self.message = None

    def _should_trigger(self, client: LoggingClient) -> bool:
        bid, ask = client.get_current_price(self.symbol)
        result = False
        bid_ask = ""
        if self.bid_ask == BidAsk.BID:
            result = self.operator(bid, self.threshold_value)
            bid_ask  = "bid"
            price = bid
        else:
            result = self.operator(ask, self.threshold_value)
            bid_ask = "ask"
            price = ask

        if result:
            self._trigger(bid_ask, price)
            return True
        else:
            self._untrigger()

if __name__ == '__main__':
    gold_spot_price = XTBSpotAlert(name="Gold Spot Price XTB Alert",
                            description="Alert when gold spot price is above 1800",
                            schedule="* * * * *",
                            type="spot",
                            data_source="XTB",
                            operator=operator.gt,
                            threshold_value=1800.0,
                            symbol="XAUUSD",
                            bid_ask=BidAsk.ASK,
                            action=AlertAction.PRINT_MESSAGE,
                            message="Gold spot price is above 1800")
