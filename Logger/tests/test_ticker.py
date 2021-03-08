import pytest
import unittest
from ticker import Ticker
from datetime import datetime

class TestTicker(unittest.TestCase):

    def test_ticker_raises_exception(self):
        with self.assertRaises(Exception) as context:
            t = Ticker('16m')
        self.assertTrue('Timeframe' in str(context.exception))

    def test_tick_1minute_true(self):
        #Arrange
        year = 2020
        month = 1
        day = 1
        hour = 13
        minute = 15
        second = 1
        d = datetime(year, month, day, hour, minute, second)
        t = Ticker('1m')

        #Act
        result = t.tick(d)

        #Assert
        self.assertTrue(result)

    def test_tick_1minute_false(self):
        #Arrange
        year = 2020
        month = 1
        day = 1
        hour = 13
        minute = 15
        second = 0
        d = datetime(year, month, day, hour, minute, second)
        t = Ticker('1m')
        #Act
        result = t.tick(d)
        #Assert
        self.assertFalse(result)

    def test_tick_5minute_true(self):
        #Arrange
        year = 2020
        month = 1
        day = 1
        hour = 13
        minute = 5
        second = 1
        d = datetime(year, month, day, hour, minute, second)
        t = Ticker('5m')
        #Act
        result = t.tick(d)
        #Assert
        self.assertTrue(result)

        #Arrange
        minute = 10
        d = datetime(year, month, day, hour, minute, second)
        #Act
        result = t.tick(d)
        #Assert
        self.assertTrue(result)

        #Arrange
        minute = 0
        d = datetime(year, month, day, hour, minute, second)
        #Act
        result = t.tick(d)
        #Assert
        self.assertTrue(result)

    def test_tick_5minute_false(self):
        #Arrange
        year = 2020
        month = 1
        day = 1
        hour = 13
        minute = 5
        second = 0
        d = datetime(year, month, day, hour, minute, second)
        t = Ticker('5m')
        #Act
        result = t.tick(d)
        #Assert
        self.assertFalse(result)

        #Arrange
        minute = 11
        second = 1
        d = datetime(year, month, day, hour, minute, second)
        #Act
        result = t.tick(d)
        #Assert
        self.assertFalse(result)

        #Arrange
        minute = 0
        second = 5
        d = datetime(year, month, day, hour, minute, second)
        #Act
        result = t.tick(d)
        #Assert
        self.assertFalse(result)

    def test_tick_15minute_true(self):
        #Arrange
        year = 2020
        month = 1
        day = 1
        hour = 13
        minute = 15
        second = 1
        d = datetime(year, month, day, hour, minute, second)
        t = Ticker('15m')
        #Act
        result = t.tick(d)
        #Assert
        self.assertTrue(result)

        #Arrange
        minute = 30
        d = datetime(year, month, day, hour, minute, second)
        #Act
        result = t.tick(d)
        #Assert
        self.assertTrue(result)

        #Arrange
        minute = 0
        d = datetime(year, month, day, hour, minute, second)
        #Act
        result = t.tick(d)
        #Assert
        self.assertTrue(result)

    def test_tick_15minute_false(self):
        #Arrange
        year = 2020
        month = 1
        day = 1
        hour = 13
        minute = 15
        second = 0
        d = datetime(year, month, day, hour, minute, second)
        t = Ticker('15m')
        #Act
        result = t.tick(d)
        #Assert
        self.assertFalse(result)

        #Arrange
        minute = 5
        second = 1
        d = datetime(year, month, day, hour, minute, second)
        #Act
        result = t.tick(d)
        #Assert
        self.assertFalse(result)

        #Arrange
        minute = 0
        second = 5
        d = datetime(year, month, day, hour, minute, second)
        #Act
        result = t.tick(d)
        #Assert
        self.assertFalse(result)

    def test_tick_30minute_true(self):
        #Arrange
        year = 2020
        month = 1
        day = 1
        hour = 13
        minute = 30
        second = 1
        d = datetime(year, month, day, hour, minute, second)
        t = Ticker('30m')
        #Act
        result = t.tick(d)
        #Assert
        self.assertTrue(result)

        #Arrange
        minute = 30
        d = datetime(year, month, day, hour, minute, second)
        #Act
        result = t.tick(d)
        #Assert
        self.assertTrue(result)

        #Arrange
        minute = 0
        hour = 0
        d = datetime(year, month, day, hour, minute, second)
        #Act
        result = t.tick(d)
        #Assert
        self.assertTrue(result)

    def test_tick_30minute_false(self):
        #Arrange
        year = 2020
        month = 1
        day = 1
        hour = 13
        minute = 15
        second = 0
        d = datetime(year, month, day, hour, minute, second)
        t = Ticker('30m')
        #Act
        result = t.tick(d)
        #Assert
        self.assertFalse(result)

        #Arrange
        minute = 5
        second = 1
        d = datetime(year, month, day, hour, minute, second)
        #Act
        result = t.tick(d)
        #Assert
        self.assertFalse(result)

        #Arrange
        minute = 0
        second = 5
        d = datetime(year, month, day, hour, minute, second)
        #Act
        result = t.tick(d)
        #Assert
        self.assertFalse(result)

    def test_tick_1hour_true(self):
        #Arrange
        year = 2020
        month = 1
        day = 1
        hour = 13
        minute = 0
        second = 1
        d = datetime(year, month, day, hour, minute, second)
        t = Ticker('1h')
        #Act
        result = t.tick(d)
        #Assert
        self.assertTrue(result)

        #Arrange
        hour = 0
        d = datetime(year, month, day, hour, minute, second)
        #Act
        result = t.tick(d)
        #Assert
        self.assertTrue(result)

    def test_tick_1hour_false(self):
        #Arrange
        year = 2020
        month = 1
        day = 1
        hour = 13
        minute = 15
        second = 0
        d = datetime(year, month, day, hour, minute, second)
        t = Ticker('1h')
        #Act
        result = t.tick(d)
        #Assert
        self.assertFalse(result)

        #Arrange
        hour = 5
        minute = 0
        second = 2
        d = datetime(year, month, day, hour, minute, second)
        #Act
        result = t.tick(d)
        #Assert
        self.assertFalse(result)

        #Arrange
        minute = 2
        second = 1
        d = datetime(year, month, day, hour, minute, second)
        #Act
        result = t.tick(d)
        #Assert
        self.assertFalse(result)

    def test_tick_5hour_true(self):
        #Arrange
        year = 2020
        month = 1
        day = 1
        hour = 15
        minute = 0
        second = 1
        d = datetime(year, month, day, hour, minute, second)
        t = Ticker('5h')
        #Act
        result = t.tick(d)
        #Assert
        self.assertTrue(result)

        #Arrange
        hour = 0
        d = datetime(year, month, day, hour, minute, second)
        #Act
        result = t.tick(d)
        #Assert
        self.assertTrue(result)

    def test_tick_5hour_false(self):
        #Arrange
        year = 2020
        month = 1
        day = 1
        hour = 13
        minute = 15
        second = 0
        d = datetime(year, month, day, hour, minute, second)
        t = Ticker('5h')
        #Act
        result = t.tick(d)
        #Assert
        self.assertFalse(result)

        #Arrange
        hour = 5
        minute = 0
        second = 2
        d = datetime(year, month, day, hour, minute, second)
        #Act
        result = t.tick(d)
        #Assert
        self.assertFalse(result)

        #Arrange
        hour = 5
        minute = 2
        second = 1
        d = datetime(year, month, day, hour, minute, second)
        #Act
        result = t.tick(d)
        #Assert
        self.assertFalse(result)

    def test_tick_1Day_true(self):
        #Arrange
        year = 2020
        month = 1
        day = 1
        hour = 12
        minute = 0
        second = 1
        d = datetime(year, month, day, hour, minute, second)
        t = Ticker('1D')
        #Act
        result = t.tick(d)
        #Assert
        self.assertTrue(result)

        #Arrange
        hour = 12
        day = 2
        d = datetime(year, month, day, hour, minute, second)
        #Act
        result = t.tick(d)
        #Assert
        self.assertTrue(result)

    def test_tick_1Day_false(self):
        #Arrange
        year = 2020
        month = 1
        day = 1
        hour = 10
        minute = 0
        second = 1
        d = datetime(year, month, day, hour, minute, second)
        t = Ticker('1D')
        #Act
        result = t.tick(d)
        #Assert
        self.assertFalse(result)

        #Arrange
        hour = 12
        day = 2
        minute = 1
        d = datetime(year, month, day, hour, minute, second)
        #Act
        result = t.tick(d)
        #Assert
        self.assertFalse(result)

    def test_tick_1Week_true(self):
        #Arrange
        year = 2021
        month = 3
        day = 8
        hour = 12
        minute = 0
        second = 1
        d = datetime(year, month, day, hour, minute, second)
        t = Ticker('1W')
        #Act
        result = t.tick(d)
        #Assert
        self.assertTrue(result)

        #Arrange
        hour = 12
        day = 22
        d = datetime(year, month, day, hour, minute, second)
        #Act
        result = t.tick(d)
        #Assert
        self.assertTrue(result)

    def test_tick_1Week_false(self):
        #Arrange
        year = 2021
        month = 3
        day = 2
        hour = 12
        minute = 0
        second = 1
        d = datetime(year, month, day, hour, minute, second)
        t = Ticker('1W')
        #Act
        result = t.tick(d)
        #Assert
        self.assertFalse(result)

        #Arrange
        hour = 14
        day = 8
        d = datetime(year, month, day, hour, minute, second)
        #Act
        result = t.tick(d)
        #Assert
        self.assertFalse(result)
if __name__ == '__main__':
    unittest.main()
