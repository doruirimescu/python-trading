from Trading.live.alert.alert import AlertAction
from Trading.live.alert.xtb_alert import XTBSpotAlert
from Trading.live.client.client import LoggingClient
from unittest import TestCase
from unittest.mock import MagicMock
from Trading.model.price import BidAsk
import operator

class TestAlert(TestCase):
    def test_xtb_spot_alert(self):
        client = MagicMock(spec_set=LoggingClient(None, None))
        client.get_current_price.return_value = (1800.1, 1800.2)
        client.is_market_open.return_value = True


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
                            message="Gold spot price is above 1800",
                            client=client)



        gold_spot_price.evaluate()
        self.assertTrue(gold_spot_price.is_triggered)
        self.assertEqual(gold_spot_price.message, "XAUUSD ask price of 1800.2 is > 1800.0 from datasource: XTB")
