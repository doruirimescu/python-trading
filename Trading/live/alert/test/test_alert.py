from Trading.live.alert.alert import Alert, Operator, get_minimum_monitoring_timeframe_seconds
from Trading.instrument import Timeframe
from unittest import TestCase

def mock_data_getter(client):
    return 0.0

class TestAlert(TestCase):
    def test_get_minimum_monitoring_timeframe_seconds(self):
        def mock_data_getter(client):
            return 0.0
        alert_1 = Alert(description="Monitor gold prices",
                        operator=Operator.LESS_THAN,
                        value=1800.0,
                        monitoring_timeframe=Timeframe('1h'),
                        data_getter=mock_data_getter)
        alert_2 = Alert(description="Monitor silver prices",
                        operator=Operator.GREATER_THAN,
                        value=25.0,
                        monitoring_timeframe=Timeframe('1m'),
                        data_getter=mock_data_getter)
        alerts = [alert_1, alert_2]
        result = get_minimum_monitoring_timeframe_seconds(alerts)
        self.assertEqual(result, 60)
