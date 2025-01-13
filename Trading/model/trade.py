from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional, List, Tuple


@dataclass
class MaxDrawdown:
    date: datetime
    value: float

    def dict(self):
        return {k: str(v) for k, v in asdict(self).items()}

@dataclass
class TradeOrder:
    cmd: int  # 0 buy, 1 sell
    date: datetime
    price: float
    volume: float
    symbol: str

@dataclass
class BuyTradeOrder(TradeOrder):
    cmd: int = field(default=0, init=False)

@dataclass
class SellTradeOrder(TradeOrder):
    cmd: int = field(default=1, init=False)

@dataclass
class Trade:
    cmd: int  # 0 buy, 1 sell
    entry_date: datetime
    exit_date: Optional[datetime] = None
    open_price: Optional[float] = None
    close_price: Optional[float] = None
    max_drawdown: Optional[MaxDrawdown] = None
    symbol: Optional[str] = None
    profit: Optional[float] = None
    volume: Optional[float] = None

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
        self.max_drawdown = MaxDrawdown(
            date=drawdown_date, value=round(max_drawdown, 3)
        )

    def dict(self):
        return {k: str(v) for k, v in asdict(self).items()}

    def get_orders(self) -> Tuple[BuyTradeOrder, SellTradeOrder]:
        return (BuyTradeOrder(date=self.entry_date, price=self.open_price, volume=self.volume, symbol=self.symbol),
                SellTradeOrder(date=self.exit_date, price=self.close_price, volume=self.volume, symbol=self.symbol))

# create BuyTrade that inherits from Trade, has cmd=0
@dataclass
class BuyTrade(Trade):
    cmd: int = field(default=0, init=False)

@dataclass
class SellTrade(Trade):
    cmd: int = field(default=1, init=False)

class StrategySummary:
    def __init__(
        self,
        should_reinvest: bool,
        desired_cash_invested: int,
        contract_size: int,
        profit_currency: str,
        category_name: str,
    ) -> None:
        # TODO: move all the analyze code here.
        self.should_reinvest = should_reinvest
        self.desired_cash_invested = desired_cash_invested
        self.contract_size = contract_size
        self.profit_currency = profit_currency
        self.category_name = (category_name,)
        self.print_annualized_returns = False

    def _calculate(self):
        pass

    def print(self):
        pass


@dataclass
class TradesAnalysisResult:
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
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

    def dict(self):
        return {k: str(v) for k, v in asdict(self).items()}

    def print(self):
        print("---------------------------------------")
        print(f"From: {self.from_date.date()} to {self.to_date.date()}")
        print(f"Total net profit: {self.total_net_profit:.2f} {self.profit_currency}")
        print(f"Total cash invested: {self.total_cash_invested:.2f} {self.profit_currency}")
        print(
            f"Average cash invested per trade: {self.average_cash_per_trade:.2f} {self.profit_currency}"
        )
        print(
            f"Max drawdown: {self.max_drawdown:.2f} {self.profit_currency} between {self.drawdown_date_start} and {self.drawdown_date_end}"
        )
        print(f"A number of {self.n_trades} trades were made during {self.n_days} days (with overlaps)")
        print(
            f"Profit trades: {self.n_profit_trades}, Loss trades: {self.n_loss_trades} Win ratio: {100*self.n_profit_trades/self.n_trades:.2f}%"
        )
        print(f"Reward to risk ratio: {self.rewards_to_risk_ratio:.2f}")
        print(f"Average trade duration: {self.average_trade_duration_days:.2f} days")
        print(f"Annualized returns: {self.annualized_return:.2f}%")

def aggregate_analysis_results(results: List[TradesAnalysisResult]):
    total_net_profit = 0
    total_cash_invested = 0
    max_loss = 1000000
    n_profit_trades = 0
    n_loss_trades = 0
    total_loss = 0
    n_years = 0
    n_days = 0
    n_trades = 0
    annualized_return = 0
    average_cash_per_trade = 0
    rewards_to_risk_ratio = 0
    average_trade_duration_days = 0
    print(f"A total of {len(results)} results were aggregated")
    for result in results:
        total_net_profit += result.total_net_profit
        total_cash_invested += result.total_cash_invested
        if result.max_loss < max_loss:
            max_loss = result.max_loss
        n_profit_trades += result.n_profit_trades

        if result.n_loss_trades:
            n_loss_trades += result.n_loss_trades

        rewards_to_risk_ratio += result.rewards_to_risk_ratio
        total_loss += result.total_loss
        n_years += result.n_years
        n_days += result.n_days
        n_trades += result.n_trades
        annualized_return += result.annualized_return
        average_cash_per_trade += result.average_cash_per_trade
        average_trade_duration_days += result.average_trade_duration_days
    annualized_return /= len(results)
    average_cash_per_trade /= len(results)
    rewards_to_risk_ratio /= len(results)
    average_trade_duration_days /= len(results)
    tar = TradesAnalysisResult(
        from_date=results[0].from_date,
        to_date=results[0].to_date,
        total_net_profit=total_net_profit,
        total_cash_invested=total_cash_invested,
        max_loss=max_loss,
        n_profit_trades=n_profit_trades,
        n_loss_trades=n_loss_trades,
        total_loss=total_loss,
        n_years=n_years,
        n_days=n_days,
        n_trades=n_trades,
        annualized_return=annualized_return,
        profit_currency=results[0].profit_currency,
        average_cash_per_trade=average_cash_per_trade,

        max_drawdown=results[0].max_drawdown,
        drawdown_date_start=results[0].drawdown_date_start,
        drawdown_date_end=results[0].drawdown_date_end,

        rewards_to_risk_ratio=rewards_to_risk_ratio,
        average_trade_duration_days=average_trade_duration_days,

    )
    return tar

def analyze_trades(trades: List[Trade], strategy_summary: StrategySummary):
    from Trading.symbols.constants import (
        XTB_ALL_SYMBOLS_DICT,
    )

    all_dates = [t.entry_date for t in trades] + [t.exit_date for t in trades]
    all_dates = sorted(list(set(all_dates)))
    if len(all_dates) < 2:
        return None

    n_days = (all_dates[-1] - all_dates[0]).days

    (SHOULD_REINVEST, DESIRED_CASH_INVESTED) = (
        strategy_summary.should_reinvest,
        strategy_summary.desired_cash_invested,
    )

    trade_analysis_result = TradesAnalysisResult()
    trade_analysis_result.from_date = all_dates[0]
    trade_analysis_result.to_date = all_dates[-1]
    trade_analysis_result.total_net_profit = 0
    trade_analysis_result.total_cash_invested = 0
    trade_analysis_result.max_drawdown = 1000000
    trade_analysis_result.max_loss = trade_analysis_result.max_drawdown
    trade_analysis_result.n_profit_trades = 0
    trade_analysis_result.n_loss_trades = 0
    trade_analysis_result.total_loss = 0
    trade_analysis_result.total_profit = 0
    trade_analysis_result.n_days = n_days
    trade_analysis_result.n_years = trade_analysis_result.n_days / 365.0
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
        trade_analysis_result.max_drawdown = min(
            trade_analysis_result.max_drawdown, t.max_drawdown.value
        )
        profits_list.append(trade_analysis_result.total_net_profit)
        if p < 0:
            trade_analysis_result.n_loss_trades += 1
            trade_analysis_result.total_loss += p
        else:
            trade_analysis_result.n_profit_trades += 1
            trade_analysis_result.total_profit += p
    trade_analysis_result.average_cash_per_trade = (
        trade_analysis_result.total_cash_invested / len(trades)
    )
    trade_analysis_result.average_trade_duration_days = (
        trade_analysis_result.average_trade_duration_days / len(trades)
    )

    for t in trades:
        if t.max_drawdown.value == trade_analysis_result.max_drawdown:
            trade_analysis_result.drawdown_date_start = t.entry_date.date()
            trade_analysis_result.drawdown_date_end = t.max_drawdown.date.date()
    try:
        trade_analysis_result.rewards_to_risk_ratio = abs(
            trade_analysis_result.total_profit / trade_analysis_result.total_loss
        )
    except ZeroDivisionError:
        trade_analysis_result.rewards_to_risk_ratio = 100

    annualized_return = (
            trade_analysis_result.total_net_profit
        / trade_analysis_result.total_cash_invested
    ) * 365 / trade_analysis_result.n_days
    trade_analysis_result.annualized_return = 100 * annualized_return

    return trade_analysis_result
