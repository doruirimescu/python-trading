from Trading.config.config import ALERTS_PATH
from Trading.live.alert.alert import SpotAlert, AlertAction
from Trading.live.alert.yfinance_alert import YFinanceSpotAlert
from Trading.model.price import BidAsk
import operator
from typing import List
import json
from stateful_data_processor.file_rw import JsonFileRW
import sys

def dump_alerts_to_json(alerts: List):
    json_file = JsonFileRW(ALERTS_PATH)
    jsons = [json.loads(alert.custom_json()) for alert in alerts]
    json_file.write(jsons)

def generate_yfinance_alert_gt(
    stock_name: str,
    stock_symbol: str,
    threshold: int,
    bid_ask: BidAsk = BidAsk.ASK,
    action: AlertAction = AlertAction.SEND_EMAIL,
):
    return YFinanceSpotAlert(
        name=f"{stock_name} Spot Price XTB Alert",
        description=f"Alert when {stock_name} spot price is above {threshold}",
        schedule="* * * * *",
        type="spot",
        data_source="YFinance",
        operator=operator.gt,
        threshold_value=threshold,
        symbol=stock_symbol,
        bid_ask=bid_ask,
        action=action,
        message=f"{stock_name} spot price is above {threshold}",
    )

def generate_xtb_alert_lt(
    stock_name: str,
    stock_symbol: str,
    threshold: int,
    bid_ask: BidAsk = BidAsk.BID,
    action: AlertAction = AlertAction.SEND_EMAIL,
):
    return YFinanceSpotAlert(
        name=f"{stock_name} Spot Price YFinance Alert",
        description=f"Alert when {stock_name} spot price is below {threshold}",
        schedule="* * * * *",
        type="spot",
        data_source="YFinance",
        operator=operator.lt,
        threshold_value=threshold,
        symbol=stock_symbol,
        bid_ask=bid_ask,
        action=action,
        message=f"{stock_name} spot price is below {threshold}",
    )

def print_alerts(alerts: List[SpotAlert], filter_list: List[str] = []):
    alerts.sort(key=lambda x: x.symbol)
    if filter_list:
        alerts = [alert for alert in alerts if alert.symbol in filter_list]
    for alert in alerts:
        # Just print the description and add the message if the alert is triggered
        print(alert.description)
        if alert.is_triggered:
            print(alert.message)

if __name__ == "__main__":
    # generate_alerts_to_json()
    json_file = JsonFileRW(ALERTS_PATH)
    data = json_file.read()
    alerts = []
    for alert in data:
        try:
            if alert.get("data_source") == "YFinance" and alert.get("type") == "spot":
                a = YFinanceSpotAlert.custom_load(json.dumps(alert))
                alerts.append(a)
            else:
                print(f"Unknown alert type or data source: {alert}")
        except Exception as e:
            print(f"Error loading alert: {e}")
            sys.exit(0)
            continue
    print_alerts(alerts)

    for alert in alerts:
        company_name = alert.name
        alert.evaluate()
        #print(alert)
    dump_alerts_to_json(alerts)
