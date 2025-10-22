from Trading.live.alert.alert import SpotAlert
from typing import Optional
from pydantic import ConfigDict

import yfinance as yf
class YFinanceSpotAlert(SpotAlert):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    # configure field ticker to not be included in serialization

    _ticker: Optional[dict] = None
    _ticker_info: Optional[dict] = None

    def model_post_init(self, __context):
        self._ticker = yf.Ticker(self.symbol)
        self._ticker_info = self._ticker.info

    def are_conditions_valid(self) -> bool:
        return self._is_market_open()

    def _get_current_price(self):
        return self._ticker_info.get('bid'), self._ticker_info.get('ask')

    def _is_market_open(self) -> bool:
        market_state = self._ticker_info.get("marketState", "").upper()
        return market_state in {"REGULAR", "OPEN"}

if __name__ == "__main__":
    from Trading.model.price import BidAsk
    import operator
    from Trading.model.price import BidAsk
    from Trading.live.alert.alert import AlertAction
    sxr8_yfinance_alert = YFinanceSpotAlert(
        name="SXR8 Spot Price YFinance Alert",
        description="Alert when SXR8 spot price is above 70",
        schedule="* * * * *",
        type="spot",
        data_source="YFinance",
        operator=operator.gt,
        threshold_value=700.0,
        symbol="SXR8.DE",
        bid_ask=BidAsk.ASK,
        action=AlertAction.PRINT_MESSAGE,
        message="SXR8 spot price is above 70",
    )
    sxr8_yfinance_alert.evaluate()
    print(sxr8_yfinance_alert)
