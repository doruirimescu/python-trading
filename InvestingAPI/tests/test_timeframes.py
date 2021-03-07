import pytest
import unittest
import datetime
import timeframes

class TestTimeframes(unittest.TestCase):

    def test_timeframesToMinutes1(self):
        self.assertEqual(timeframes.TIMEFRAME_TO_MINUTES['1m'], 1)
        self.assertEqual(timeframes.TIMEFRAME_TO_MINUTES['5m'], 5)
        self.assertEqual(timeframes.TIMEFRAME_TO_MINUTES['15m'], 15)
        self.assertEqual(timeframes.TIMEFRAME_TO_MINUTES['30m'], 30)
        self.assertEqual(timeframes.TIMEFRAME_TO_MINUTES['1h'], 60)
        self.assertEqual(timeframes.TIMEFRAME_TO_MINUTES['5h'], 300)
        self.assertEqual(timeframes.TIMEFRAME_TO_MINUTES['1D'], 1440)
        self.assertEqual(timeframes.TIMEFRAME_TO_MINUTES['1W'], 10080)
        self.assertEqual(timeframes.TIMEFRAME_TO_MINUTES['1M'], 43200)

if __name__ == '__main__':
    unittest.main()
