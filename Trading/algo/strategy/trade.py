from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List


@dataclass
class MaxDrawdown:
    date: datetime
    value: float


@dataclass
class Trade:
    cmd: int  # 0 buy, 1 sell
    entry_date: datetime
    exit_date: Optional[datetime] = None
    open_price: Optional[float] = None
    close_price: Optional[float] = None
    symbol: Optional[str] = None
    max_drawdown: Optional[MaxDrawdown] = None

    def duration_days(self):
        return (self.exit_date - self.entry_date).days

    def calculate_max_drawdown_price_diff(self, historical_data):
        max_drawdown = 1000000
        drawdown_date = None
        for i, d in enumerate(historical_data["date"]):
            if isinstance(d, str):
                d = datetime.fromisoformat(d)
            if d >= self.entry_date and d <= self.exit_date:
                if self.cmd == 0:
                    lowest = 0
                    if "low" in historical_data:
                        lowest = historical_data["low"][i]
                    else:
                        lowest = historical_data["close"][i]
                    max_drawdown = min(max_drawdown, lowest - self.open_price)
                    drawdown_date = d
        self.max_drawdown = MaxDrawdown(date=drawdown_date, value=max_drawdown)


class StrategySummary:
    def __init__(
        self,
        n_days: int,
        should_reinvest: bool,
        desired_cash_invested: int,
        contract_size: int,
        profit_currency: str,
        category_name: str,
    ) -> None:
        # TODO: move all the analyze code here.
        self.n_days = n_days
        self.should_reinvest = should_reinvest
        self.desired_cash_invested = desired_cash_invested
        self.contract_size = contract_size
        self.profit_currency = profit_currency
        self.category_name = category_name,
        self.print_annualized_returns = False


    def _calculate(self):
        pass

    def print(self):
        pass


def analyze_trades(
    trades: List[Trade], strategy_summary: StrategySummary
):
    from Trading.symbols.constants import (
        XTB_ALL_SYMBOLS_DICT,
    )

    (N_DAYS, SHOULD_REINVEST, DESIRED_CASH_INVESTED, PRINT_ANNUALIZED_RETURNS) = (
        strategy_summary.n_days,
        strategy_summary.should_reinvest,
        strategy_summary.desired_cash_invested,
        strategy_summary.print_annualized_returns,
    )

    total_net_profit = 0
    total_cash_invested = 0
    max_drawdown = 1000000
    max_loss = max_drawdown
    n_profit_trades = 0
    n_loss_trades = 0
    total_loss = 0
    total_profit = 0
    profits_list = []
    average_trade_duration_days = 0
    for t in trades:
        symbol_info = XTB_ALL_SYMBOLS_DICT[t.symbol]
        CONTRACT_SIZE = symbol_info["contractSize"]
        PROFIT_CURRENCY = symbol_info["currencyProfit"]
        CATEGORY_NAME = symbol_info["categoryName"]

        average_trade_duration_days += t.duration_days()
        if SHOULD_REINVEST:
            cash_to_invest = DESIRED_CASH_INVESTED + total_profit
        else:
            cash_to_invest = DESIRED_CASH_INVESTED

        volume = (cash_to_invest) / (t.open_price * CONTRACT_SIZE)

        if CATEGORY_NAME == "IND":
            volume = round(volume, 2)
            volume = max(0.01, volume)
        elif CATEGORY_NAME == "ETF" or CATEGORY_NAME == "STC":
            volume = int(volume)

        actual_cash_invested = volume * t.open_price * CONTRACT_SIZE
        p = CONTRACT_SIZE * volume * (t.close_price - t.open_price)

        total_cash_invested += actual_cash_invested

        if p < max_loss:
            max_loss = p
        total_net_profit += p
        max_drawdown = min(max_drawdown, t.max_drawdown.value)
        profits_list.append(total_net_profit)
        if p < 0:
            n_loss_trades += 1
            total_loss += p
        else:
            n_profit_trades += 1
            total_profit += p
    average_cash_per_trade = total_cash_invested / len(trades)
    average_trade_duration_days = average_trade_duration_days / len(trades)

    print(f"Total net profit: {total_net_profit:.2f} {PROFIT_CURRENCY}")
    print(
        f"Average cash invested per trade: {average_cash_per_trade:.2f} {PROFIT_CURRENCY}"
    )
    for t in trades:
        if t.max_drawdown.value == max_drawdown:
            entry_date = t.entry_date.date()
            drawdown_date = t.max_drawdown.date.date()
            print(
                f"Max drawdown {max_drawdown:.2f} {PROFIT_CURRENCY} between {entry_date} and {drawdown_date}"
            )

    print(f"A number of {len(trades)} trades were made during {N_DAYS} days")
    print(
        f"Profit trades: {n_profit_trades}, Loss trades: {n_loss_trades} Win ratio: {100*n_profit_trades/len(trades):.2f}%"
    )
    print(f"Reward to risk ratio: {abs(total_profit/total_loss):.2f}")
    print(f"Average trade duration: {average_trade_duration_days:.2f} days")

    n_years = N_DAYS / 365.0

    annualized_return = (
        (total_net_profit + average_cash_per_trade) / average_cash_per_trade
    ) ** (1 / n_years) - 1
    print(f"Annualized returns: {100*annualized_return:.2f}%")

    if PRINT_ANNUALIZED_RETURNS:
        pass

    if 100 * annualized_return > 10.0:
        return 100 * annualized_return
    else:
        return None
