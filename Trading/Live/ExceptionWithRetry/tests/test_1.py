import pytest
import unittest
from typing import List

from Trading.Live.ExceptionWithRetry.exceptionwithretry import ExceptionWithRetry, exception_with_retry

@exception_with_retry(3, 0.5)
def wrapped_method(number_1: int, number_2: int = 0, calls: List = []):
    calls.append(1)
    if number_1 < 0:
        raise Exception("Not gonna happen")
    else:
        return number_1 + number_2

class TestMethods:
    def method(self, arg):
        arg.append(arg[-1] + 20)
        raise Exception("Not gonna happen")

def method(arg):
    arg.append(arg[-1] + 1)
    raise Exception("Not gonna happen")

def method2(arg1, arg2):
    arg1.append(arg1[-1] + arg2)
    raise Exception("Not gonna happen")

def method3():
    return 25

def method_caller(arg):
    method(arg)
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

    def test_4(self):
        ewr = ExceptionWithRetry(method_caller, 2, 0.0)
        arg =[1,2]
        ewr.run([arg])
        self.assertEqual(arg, [1,2,3,4])

    def test_5(self):
        t = TestMethods()
        ewr = ExceptionWithRetry(t.method, 5, 0.0)
        arg = [0]
        ewr.run([arg])
        self.assertEqual(arg, [0, 20, 40, 60, 80, 100])

    def test_6(self):
        ewr = ExceptionWithRetry(method3, 5, 0.0)
        result = ewr.run([])
        self.assertEqual(result, 25)


class TestExceptionWithRetryDecorator(unittest.TestCase):
    def test_no_exception(self):
        result = wrapped_method(number_1=1)
        self.assertEqual(1, result)

        calls = []
        result = wrapped_method(number_1=1, number_2=10, calls=calls)
        self.assertEqual(11, result)
        self.assertEqual(1, len(calls))

    def test_throws_exception(self):
        with self.assertRaises(Exception):
            calls = []
            result = wrapped_method(-1, 0, calls)
            self.assertEqual(3, len(calls))

        with self.assertRaises(Exception):
            calls = []
            wrapped_method(number_1=-1, number_2=2)
            self.assertEqual(3, len(calls))

        with self.assertRaises(Exception):
            calls = []
            wrapped_method(-1, 2)
            self.assertEqual(3, len(calls))
