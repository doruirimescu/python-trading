import pytest
import unittest
import datetime
from Trading.live.investing_api.investing_candlestick import PatternAnalysis
from Trading.live.investing_api.investing_candlestick import PatternReliability

class TestPatternAnalysis(unittest.TestCase):
    def test_isMoreReliableThan_High_None(self):
        p1 = PatternAnalysis("p1", PatternReliability.HIGH)
        p2 = PatternAnalysis("p1", None)
        self.assertEqual(p1.isMoreReliableThan(p2), True)

    def test_isMoreReliableThan_High_High(self):
        p1 = PatternAnalysis("p1", PatternReliability.HIGH)
        p2 = PatternAnalysis("p2", PatternReliability.HIGH)
        self.assertEqual(p1.isMoreReliableThan(p2), False)

    def test_isMoreReliableThan_High_Medium(self):
        p1 = PatternAnalysis("p1", PatternReliability.HIGH)
        p2 = PatternAnalysis("p2", PatternReliability.MEDIUM)
        self.assertEqual(p1.isMoreReliableThan(p2), True)

    def test_isMoreReliableThan_Medium_High(self):
        p1 = PatternAnalysis("Engulfing Bearish", PatternReliability.MEDIUM)
        p2 = PatternAnalysis("Three Inside Up", PatternReliability.HIGH)
        self.assertEqual(p1.isMoreReliableThan(p2), False)

    def test_isMoreReliableThan_Medium_Medium(self):
        p1 = PatternAnalysis("Engulfing Bearish", PatternReliability.MEDIUM)
        p2 = PatternAnalysis("Three Inside Up", PatternReliability.HIGH)
        self.assertEqual(p1.isMoreReliableThan(p2), False)

    def test_isMoreReliableThan_Medium_Low(self):
        p1 = PatternAnalysis("Engulfing Bearish", PatternReliability.MEDIUM)
        p2 = PatternAnalysis("Three Inside Up", PatternReliability.LOW)
        self.assertEqual(p1.isMoreReliableThan(p2), True)

    def test_isMoreReliableThan_Low_High(self):
        p1 = PatternAnalysis("Engulfing Bearish", PatternReliability.LOW)
        p2 = PatternAnalysis("Three Inside Up", PatternReliability.HIGH)
        self.assertEqual(p1.isMoreReliableThan(p2), False)

    def test_isMoreReliableThan_Low_Medium(self):
        p1 = PatternAnalysis("Engulfing Bearish", PatternReliability.LOW)
        p2 = PatternAnalysis("Three Inside Up", PatternReliability.HIGH)
        self.assertEqual(p1.isMoreReliableThan(p2), False)

    def test_isMoreReliableThan_Low_Low(self):
        p1 = PatternAnalysis("Engulfing Bearish", PatternReliability.LOW)
        p2 = PatternAnalysis("Three Inside Up", PatternReliability.HIGH)
        self.assertEqual(p1.isMoreReliableThan(p2), False)


if __name__ == '__main__':
    unittest.main()
