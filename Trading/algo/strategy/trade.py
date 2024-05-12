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
        self.max_drawdown = MaxDrawdown(date=drawdown_date, value=round(max_drawdown, 3))


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


@dataclass
class TradesAnalysisResult:
    total_net_profit: Optional[float] = None
    total_cash_invested: Optional[float] = None
    max_drawdown: Optional[float] = None
    max_loss: Optional[float] = None
    n_profit_trades: Optional[int] = None
    n_loss_trades: Optional[int] = None
    total_loss: Optional[float] = None
    total_profit: Optional[float] = None
    average_trade_duration_days: Optional[float] = None
    rewards_to_risk_ratio: Optional[float] = None
    average_cash_per_trade: Optional[float] = None
    annualized_return: Optional[float] = None
    n_years: Optional[int] = None
    n_days: Optional[int] = None
    n_trades: Optional[int] = None
    profit_currency: Optional[str] = None
    drawdown_date_start: Optional[datetime] = None
    drawdown_date_end: Optional[datetime] = None

    def print(self):
        print("---------------------------------------")
        print(f"Total net profit: {self.total_net_profit:.2f} {self.profit_currency}")
        print(f"Average cash invested per trade: {self.average_cash_per_trade:.2f} {self.profit_currency}")
        print(f"Max drawdown: {self.max_drawdown:.2f} {self.profit_currency} between {self.drawdown_date_start} and {self.drawdown_date_end}")
        print(f"A number of {self.n_trades} trades were made during {self.n_days} days")
        print(f"Profit trades: {self.n_profit_trades}, Loss trades: {self.n_loss_trades} Win ratio: {100*self.n_profit_trades/self.n_trades:.2f}%")
        print(f"Reward to risk ratio: {self.rewards_to_risk_ratio:.2f}")
        print(f"Average trade duration: {self.average_trade_duration_days:.2f} days")
        print(f"Annualized returns: {self.annualized_return:.2f}%")
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

    trade_analysis_result = TradesAnalysisResult()
    trade_analysis_result.total_net_profit = 0
    trade_analysis_result.total_cash_invested = 0
    trade_analysis_result.max_drawdown = 1000000
    trade_analysis_result.max_loss = trade_analysis_result.max_drawdown
    trade_analysis_result.n_profit_trades = 0
    trade_analysis_result.n_loss_trades = 0
    trade_analysis_result.total_loss = 0
    trade_analysis_result.total_profit = 0
    trade_analysis_result.n_days = N_DAYS
    trade_analysis_result.n_trades = len(trades)
    profits_list = []
    trade_analysis_result.average_trade_duration_days = 0
    for t in trades:
        symbol_info = XTB_ALL_SYMBOLS_DICT[t.symbol]
        CONTRACT_SIZE = symbol_info["contractSize"]
        PROFIT_CURRENCY = symbol_info["currencyProfit"]
        CATEGORY_NAME = symbol_info["categoryName"]
        trade_analysis_result.profit_currency = PROFIT_CURRENCY

        trade_analysis_result.average_trade_duration_days += t.duration_days()
        if SHOULD_REINVEST:
            cash_to_invest = DESIRED_CASH_INVESTED + trade_analysis_result.total_profit
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

        trade_analysis_result.total_cash_invested += actual_cash_invested

        if p < trade_analysis_result.max_loss:
            trade_analysis_result.max_loss = p
        trade_analysis_result.total_net_profit += p
        trade_analysis_result.max_drawdown = min(trade_analysis_result.max_drawdown, t.max_drawdown.value)
        profits_list.append(trade_analysis_result.total_net_profit)
        if p < 0:
            trade_analysis_result.n_loss_trades += 1
            trade_analysis_result.total_loss += p
        else:
            trade_analysis_result.n_profit_trades += 1
            trade_analysis_result.total_profit += p
    trade_analysis_result.average_cash_per_trade = trade_analysis_result.total_cash_invested / len(trades)
    trade_analysis_result.average_trade_duration_days = trade_analysis_result.average_trade_duration_days / len(trades)

    for t in trades:
        if t.max_drawdown.value == trade_analysis_result.max_drawdown:
            trade_analysis_result.drawdown_date_start = t.entry_date.date()
            trade_analysis_result.drawdown_date_end = t.max_drawdown.date.date()

    trade_analysis_result.rewards_to_risk_ratio = abs(
        trade_analysis_result.total_profit / trade_analysis_result.total_loss
    )

    n_years = N_DAYS / 365.0
    trade_analysis_result.n_years = n_years

    annualized_return = (
        (trade_analysis_result.total_net_profit + trade_analysis_result.average_cash_per_trade) / trade_analysis_result.average_cash_per_trade
    ) ** (1 / n_years) - 1
    trade_analysis_result.annualized_return = 100 * annualized_return

    trade_analysis_result.print()
    return trade_analysis_result
