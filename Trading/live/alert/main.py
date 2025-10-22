from Trading.config.config import ALERTS_PATH
from Trading.live.alert.alert import SpotAlert
from Trading.live.alert.shiller_pe_alert import ShillerPeAlert
from Trading.live.alert.yfinance_alert import YFinanceSpotAlert
from typing import List
import json
from stateful_data_processor.file_rw import JsonFileRW
import sys

DISABLED = {
    'type': 'spot',
    'data_source': 'YFinance',
}

def dump_alerts_to_json(alerts: List):
    json_file = JsonFileRW(ALERTS_PATH)
    jsons = [json.loads(alert.custom_json()) for alert in alerts]
    json_file.write(jsons)

def print_alerts(alerts: List[SpotAlert], filter_list: List[str] = []):
    alerts.sort(key=lambda x: x.name)
    if filter_list:
        alerts = [alert for alert in alerts if alert.symbol in filter_list]
    for alert in alerts:
        # Just print the message and add the description if the alert is triggered
        print(alert.message)
        if alert.is_triggered:
            print(alert.description)

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
            elif alert.get("type") == "shiller_pe":
                a = ShillerPeAlert.custom_load(json.dumps(alert))
                alerts.append(a)
            elif alert.get("data_source") == DISABLED['data_source'] and alert.get("type") == DISABLED['type']:
                continue
            else:
                print(f"Unknown alert type or data source: {alert}")
        except Exception as e:
            print(f"Error loading alert: {e}")
            sys.exit(0)
            continue
    print_alerts(alerts)

    for alert in alerts:
        if alert.type == DISABLED['type'] and alert.data_source == DISABLED['data_source']:
            continue
        alert.evaluate()
    # dump_alerts_to_json(alerts)
