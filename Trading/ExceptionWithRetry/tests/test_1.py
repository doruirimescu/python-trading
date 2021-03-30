import pytest
import unittest

from Trading.ExceptionWithRetry.exceptionwithretry import ExceptionWithRetry

def method(arg):
    arg.append(arg[-1] + 1)
    raise Exception("Not gonna happen")

def method2(arg1, arg2):
    arg1.append(arg1[-1] + arg2)
    raise Exception("Not gonna happen")

class TestExceptionWithRetry(unittest.TestCase):

    def test_1(self):
        ewr = ExceptionWithRetry(method, 5, 0.0)
        arg = [0]
        ewr.run([arg])
        self.assertEqual(arg,[0,1,2,3,4,5])

    def test_2(self):
        ewr = ExceptionWithRetry(method, 0, 0.0)
        arg = [0]
        ewr.run([arg])
        self.assertEqual(arg,[0])

    def test_3(self):
        ewr = ExceptionWithRetry(method2, 2, 0.0)
        arg = [0]
        ewr.run([arg, 1])
        self.assertEqual(arg,[0,1,2])
