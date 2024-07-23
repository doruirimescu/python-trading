from Trading.live.client.client import LoggingClient
from typing import Optional
from pydantic import BaseModel, ValidationError
import json
from enum import Enum
from typing import Callable, Optional
from Trading.model.price import BidAsk
from Trading.utils.send_email import send_email
from abc import abstractmethod
from Trading.utils.operator import OPERATOR_TO_SYMBOL, NAME_TO_OPERATOR
class AlertAction(Enum):
    SEND_EMAIL = 0
    PRINT_MESSAGE = 1
    RING_BELL = 2

    @classmethod
    def from_str(cls, value: str):
        if value == 'SEND_EMAIL':
            return cls.SEND_EMAIL
        elif value == 'PRINT_MESSAGE':
            return cls.PRINT_MESSAGE
        elif value == 'RING_BELL':
            return cls.RING_BELL
        else:
            raise ValueError(f"Invalid AlertAction value: {value}")

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

    def evaluate(self, *args, **kwargs) -> bool:
        if not self._should_trigger(*args, **kwargs) or self.is_handled:
            return False
        if self.action == AlertAction.SEND_EMAIL:
            send_email(subject=self.name, body=self.message)
        elif self.action == AlertAction.PRINT_MESSAGE:
            from Trading.utils.custom_logging import get_logger
            logger = get_logger("AlertLogger")
            logger.info(self.message)
        elif self.action == AlertAction.RING_BELL:
            pass
        self.is_handled = True
        return True

    def custom_json(self):
        # Convert the model to a dict, including the comparator as its name
        data = self.model_dump()
        data['operator'] = self.operator.__name__
        data['action'] = self.action.name
        data['bid_ask'] = self.bid_ask.name
        return json.dumps(data)

    @classmethod
    def custom_load(cls, json_str):
        # Load the data from the JSON string
        data = json.loads(json_str)
        # Convert the comparator name back to the actual function
        operator_name = data.get('operator')
        if operator_name in NAME_TO_OPERATOR:
            data['operator'] = NAME_TO_OPERATOR[operator_name]
        else:
            raise ValidationError(f"Invalid operatoroperator name: {operator_name}")

        try:
            data['action'] = AlertAction.from_str(data['action'])
        except KeyError:
            raise ValidationError(f"Invalid action name: {data['action']}")

        try:
            data['bid_ask'] = BidAsk.from_str(data['bid_ask'])
        except KeyError:
            raise ValidationError(f"Invalid bid_ask name: {data['bid_ask']}")
        return cls(**data)

class XTBSpotAlert(Alert):
    symbol: str
    bid_ask: BidAsk

    def are_conditions_valid(self, client: LoggingClient) -> bool:
        is_market_open = client.is_market_open(self.symbol)
        return is_market_open

    def _trigger(self, bid_ask: str, price: float):
        self.is_triggered = True
        self.message = (f"{self.symbol} {bid_ask} price of {price} is {OPERATOR_TO_SYMBOL[self.operator]} "
                        f"{self.threshold_value} from datasource: {self.data_source}")

    def _untrigger(self):
        self.is_triggered = False
        self.is_handled = False
        # self.message = None

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
