from Trading.model.price import PriceQuote
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel

class Investment(BaseModel):
    name: str
    symbol: str
    entry_price: PriceQuote
    exit_price: Optional[PriceQuote] = None
    volume: float
    profit: Optional[float] = None
    other: Optional[dict] = None


class PreciousMetalInvestMentType(str, Enum):
    coin = "coin",
    jewelry = "jewelry",
    tableware = "tableware",
    bullion = "bullion"

class PreciousMetal(str, Enum):
    gold = "gold",
    silver = "silver",
    platinum = "platinum",
    palladium = "palladium"

class PreciousMetalInvestment(Investment):
    type: PreciousMetalInvestMentType
    weight_g: float
    purity: float


class Investments:
    from Trading.model.price import PriceQuote

    def __init__(self, investments: List[Investment]) -> None:
        self.investments_list = investments

    def get_currency(self) -> str:
        cur = self.investments_list[0].entry_price.currency
        for i in self.investments_list:
            if i.entry_price.currency != cur:
                raise ValueError(f"Ensure all investments are in the same currency. {i.name} is in {i.entry_price.currency}")
        return cur

    def get_total_invested(self) -> PriceQuote:
        total = sum([i.entry_price.price * i.volume for i in self.investments_list])
        return PriceQuote(price=total, currency=self.get_currency())

    def summarize(self) -> str:
        total_invested = self.get_total_invested()
        return f"Total invested: {total_invested.price:.2f} {total_invested.currency}\n"

class PreciousMetalInvestments:
    def __init__(self, investments: List[PreciousMetalInvestment]) -> None:
        self.investments_list = investments
        self.investments = Investments(investments)

    def get_total_invested(self) -> PriceQuote:
        return self.investments.get_total_invested()

    def get_total_pure_weight_g(self):
        metal = self.investments_list[0].symbol
        for i in self.investments_list:
            if i.symbol != metal:
                raise ValueError(f"Ensure all investments are in the same metal. {i.name} is in {i.symbol}")
        return sum([i.volume * i.weight_g * i.purity for i in self.investments_list])

    def get_total_impure_weight_g(self):
        metal = self.investments_list[0].symbol
        for i in self.investments_list:
            if i.symbol != metal:
                raise ValueError(f"Ensure all investments are in the same metal. {i.name} is in {i.symbol}")
        return sum([i.volume * i.weight_g for i in self.investments_list])

    def get_total_purity(self):
        return self.get_total_pure_weight_g() / self.get_total_impure_weight_g()

    def get_average_paid_price_per_gram(self):
        return self.get_total_invested().price / self.get_total_pure_weight_g()

    def get_average_market_price_per_gram(self):
        return sum([i.other["market_price_at_purchase"] for i in self.investments_list]) / len(self.investments_list)

    def summarize(self):
        from Trading.utils.chain_exceptions import chain_exceptions
        symbol = self.investments_list[0].symbol
        curency = self.investments.get_currency()

        exceptions = []

        r = chain_exceptions(lambda: f"Metal: {symbol}\n", exceptions, default_return="")
        r += chain_exceptions(self.investments.summarize,  exceptions, default_return="")
        r += chain_exceptions(
            lambda: f"Total {symbol} weight: {self.get_total_pure_weight_g():.2f} g\n",
            exceptions, default_return="")
        r += chain_exceptions(
            lambda: f"Total weight: {self.get_total_impure_weight_g():.2f} g\n",
            exceptions, default_return="")
        r += chain_exceptions(
            lambda: f"Total (impure) weight: {self.get_total_impure_weight_g():.2f} g\n",
            exceptions, default_return="")
        r += chain_exceptions(
            lambda: f"Total purity: {self.get_total_purity():.2f}\n",
            exceptions, default_return="")
        r += chain_exceptions(
            lambda: f"Average paid price per pure {symbol} gram: {self.get_average_paid_price_per_gram():.3f} {curency}/g\n",
            exceptions, default_return="")
        r += chain_exceptions(
            lambda: f"Average market price per pure {symbol} gram: {self.get_average_market_price_per_gram():.3f} {curency}/g\n",
            exceptions, default_return="")
        if exceptions:
            r += "Exceptions:\n"
            for e in exceptions:
                r += f"{e}\n"
        return r