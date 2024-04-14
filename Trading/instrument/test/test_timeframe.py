from unittest import TestCase
from Trading.instrument.timeframes import Timeframe, TIMEFRAMES
from Trading.instrument import TIMEFRARME_ENUM

class TestTimeframe(TestCase):
    def test_timeframe(self):
        for t in TIMEFRAMES:
            tf = Timeframe(t)
            self.assertIsInstance(tf.get_name(), str)
            self.assertIsInstance(tf.get_minutes(), int)

        tf = Timeframe('1D')
        self.assertEqual(tf.get_minutes(), 1440)
        self.assertEqual(tf.get_name(), '1-day')

        tf = Timeframe(TIMEFRARME_ENUM.ONE_MINUTE)
        self.assertEqual(tf.get_minutes(), 1)
        self.assertEqual(tf.get_name(), '1-min')

    def test_timeframe_invalid(self):
        with self.assertRaises(ValueError) as context:
            tf = Timeframe('1s')
        # assert context manager
        self.assertEqual(str(context.exception), "Timeframe period 1s is not supported")

    def test_timeframesToMinutes1(self):
        self.assertEqual(Timeframe('1m').get_minutes(), 1)
        self.assertEqual(Timeframe('5m').get_minutes(), 5)
        self.assertEqual(Timeframe('15m').get_minutes(), 15)
        self.assertEqual(Timeframe('30m').get_minutes(), 30)
        self.assertEqual(Timeframe('1h').get_minutes(), 60)
        self.assertEqual(Timeframe('4h').get_minutes(), 240)
        self.assertEqual(Timeframe('1D').get_minutes(), 1440)
        self.assertEqual(Timeframe('1W').get_minutes(), 10080)
        self.assertEqual(Timeframe('1M').get_minutes(), 43200)
