from Trading.live.client.client import XTBLoggingClient
from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.live.alert.alert import XTBSpotAlert, BidAsk, AlertAction
import operator


if __name__ == '__main__':
    gold_spot_price = XTBSpotAlert(name="Gold Spot Price XTB Alert",
                            description="Alert when gold spot price is above 1800",
                            schedule="* * * * *",
                            type="spot",
                            data_source="XTB",
                            operator=operator.gt,
                            threshold_value=1800.0,
                            symbol="GOLD",
                            bid_ask=BidAsk.ASK,
                            action=AlertAction.PRINT_MESSAGE,
                            message="Gold spot price is above 1800")
    client=XTBLoggingClient(USERNAME, PASSWORD, MODE, False)
    gold_spot_price.evaluate(client=client)
