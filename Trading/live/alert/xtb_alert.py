from Trading.live.alert.alert import SpotAlert
from Trading.live.client.client import LoggingClient
from pydantic import ConfigDict

class XTBSpotAlert(SpotAlert):
    client: LoggingClient
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def are_conditions_valid(self) -> bool:
        is_market_open = self.client.is_market_open(self.symbol)
        return is_market_open

    def _get_current_price(self):
        return self.client.get_current_price(self.symbol)

    def _is_market_open(self) -> bool:
        return self.client.is_market_open(self.symbol)
