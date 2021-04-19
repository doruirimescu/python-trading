import pytest
import unittest
import datetime
from Trading.Instrument.timeframes import TIMEFRAME_TO_MINUTES

class TestTimeframes(unittest.TestCase):

    def test_timeframesToMinutes1(self):
        self.assertEqual(TIMEFRAME_TO_MINUTES['1m'], 1)
        self.assertEqual(TIMEFRAME_TO_MINUTES['5m'], 5)
        self.assertEqual(TIMEFRAME_TO_MINUTES['15m'], 15)
        self.assertEqual(TIMEFRAME_TO_MINUTES['30m'], 30)
        self.assertEqual(TIMEFRAME_TO_MINUTES['1h'], 60)
        self.assertEqual(TIMEFRAME_TO_MINUTES['5h'], 300)
        self.assertEqual(TIMEFRAME_TO_MINUTES['1D'], 1440)
        self.assertEqual(TIMEFRAME_TO_MINUTES['1W'], 10080)
        self.assertEqual(TIMEFRAME_TO_MINUTES['1M'], 43200)

if __name__ == '__main__':
    unittest.main()
