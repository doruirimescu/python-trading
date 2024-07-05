from Trading.live.client.client import XTBLoggingClient
from Trading.config.config import USERNAME, PASSWORD, MODE, ALERTS_PATH
from Trading.live.alert.alert import XTBSpotAlert, BidAsk, AlertAction
import operator
from typing import List
import json
from stateful_data_processor.file_rw import JsonFileRW

def dump_alerts_to_json(alerts: List):
    json_file = JsonFileRW(ALERTS_PATH)
    jsons = [json.loads(alert.custom_json()) for alert in alerts]
    json_file.write(jsons)

def generate_xtb_alert_gt(
    stock_name: str,
    stock_symbol: str,
    threshold: int,
    bid_ask: BidAsk = BidAsk.ASK,
    action: AlertAction = AlertAction.SEND_EMAIL,
):
    return XTBSpotAlert(
        name=f"{stock_name} Spot Price XTB Alert",
        description=f"Alert when {stock_name} spot price is above {threshold}",
        schedule="* * * * *",
        type="spot",
        data_source="XTB",
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
    return XTBSpotAlert(
        name=f"{stock_name} Spot Price XTB Alert",
        description=f"Alert when {stock_name} spot price is below {threshold}",
        schedule="* * * * *",
        type="spot",
        data_source="XTB",
        operator=operator.lt,
        threshold_value=threshold,
        symbol=stock_symbol,
        bid_ask=bid_ask,
        action=action,
        message=f"{stock_name} spot price is below {threshold}",
    )

def generate_alerts_to_json():
    alerts = [
        generate_xtb_alert_lt(
            "GOLD", "GOLD", 1800.0, BidAsk.BID, AlertAction.SEND_EMAIL
        ),
        generate_xtb_alert_lt(
            "GOLD", "GOLD", 1900.0, BidAsk.BID, AlertAction.SEND_EMAIL
        ),
        generate_xtb_alert_gt(
            "SILVER", "SILVER", 33.0, BidAsk.ASK, AlertAction.SEND_EMAIL
        ),
        generate_xtb_alert_gt(
            "Blackline", "BL.US_9", 60.0, BidAsk.ASK, AlertAction.SEND_EMAIL
        ),
        generate_xtb_alert_gt(
            "Elekta", "EKTAB1.SE", 85.0, BidAsk.BID, AlertAction.SEND_EMAIL
        ),
        generate_xtb_alert_gt(
            "Signify", "LIGHT.NL_9", 28, BidAsk.ASK, AlertAction.SEND_EMAIL
        ),
        generate_xtb_alert_gt(
            "AGCO", "AGCO.US_9", 118, BidAsk.ASK, AlertAction.SEND_EMAIL
        ),
        generate_xtb_alert_gt(
            "Amdocs", "DOX.US_9", 90, BidAsk.ASK, AlertAction.SEND_EMAIL
        ),
        generate_xtb_alert_gt(
            "Apple Hospitality", "APLE.US_9", 16, BidAsk.ASK, AlertAction.SEND_EMAIL
        ),
        generate_xtb_alert_gt(
            "BD", "BDX.US_9", 241, BidAsk.ASK, AlertAction.SEND_EMAIL
        ),
        generate_xtb_alert_gt(
            "BioMarin", "BMRN.US_9", 90, BidAsk.ASK, AlertAction.SEND_EMAIL
        ),
        generate_xtb_alert_gt(
            "Enphase Energy", "ENPH.US", 130, BidAsk.ASK, AlertAction.SEND_EMAIL
        ),
        generate_xtb_alert_gt(
            "JB Hunt", "JBHT.US_9", 200, BidAsk.ASK, AlertAction.SEND_EMAIL
        ),
        generate_xtb_alert_gt(
            "Patterson", "PDCO.US_9", 29.5, BidAsk.ASK, AlertAction.SEND_EMAIL
        ),
        generate_xtb_alert_lt(
            "Golden Ocean", "GOGL.NO_9", 100, BidAsk.BID, AlertAction.SEND_EMAIL
        ),
        generate_xtb_alert_lt(
            "Golden Ocean", "GOGL.NO_9", 90, BidAsk.BID, AlertAction.SEND_EMAIL
        ),
        generate_xtb_alert_lt(
            "Golden Ocean", "GOGL.NO_9", 80, BidAsk.BID, AlertAction.SEND_EMAIL
        ),
    ]
    dump_alerts_to_json(alerts)

if __name__ == "__main__":
    # generate_alerts_to_json()
    alerts = []
    json_file = JsonFileRW(ALERTS_PATH)
    data = json_file.read()
    for alert in data:
        alerts.append(XTBSpotAlert.custom_load(json.dumps(alert)))
    client = XTBLoggingClient(USERNAME, PASSWORD, MODE, False)

    for alert in alerts:
        alert.evaluate(client)
        alert.message = None

    dump_alerts_to_json(alerts)
