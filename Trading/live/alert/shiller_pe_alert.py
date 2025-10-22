from Trading.live.alert.alert import Alert
from Trading.datasource.multpl.shiller_pe import get_shiller_pe
from Trading.utils.operator_util import OPERATOR_TO_SYMBOL, NAME_TO_OPERATOR



class ShillerPeAlert(Alert):
    def are_conditions_valid(self) -> bool:
        return True

    def _is_market_open(self) -> bool:
        market_state = self._ticker_info.get("marketState", "").upper()
        return market_state in {"REGULAR", "OPEN"}

    def _should_trigger(self) -> bool:
        date, shiller_pe = get_shiller_pe()
        result = self.operator(shiller_pe, self.threshold_value)

        if result:
            self._trigger("Shiller PE", shiller_pe)
            return True
        else:
            self._untrigger()
            return False

    def _trigger(self, value_name: str, value: float):
        self.is_triggered = True
        self.message = (f"{value_name} value of {value} is {OPERATOR_TO_SYMBOL[self.operator]} "
                        f"{self.threshold_value} from datasource: {self.data_source}")

    def _untrigger(self):
        self.is_triggered = False
        self.is_handled = False

if __name__ == "__main__":
    from Trading.model.price import BidAsk
    import operator
    from Trading.model.price import BidAsk
    from Trading.live.alert.alert import AlertAction
    alert = ShillerPeAlert(
        name="Shiller Pe Alert",
        description="Should not invest when Shiller PE is above 40",
        schedule="* * * * *",
        type="shiller_pe",
        data_source="multpl",
        operator=operator.gt,
        threshold_value=40.0,
        action=AlertAction.PRINT_MESSAGE,
        message="Alert when Shiller PE is above 40",
    )
    alert.evaluate()
    print(alert)
