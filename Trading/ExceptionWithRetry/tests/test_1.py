import pytest
import unittest

from Trading.ExceptionWithRetry.exceptionwithretry import ExceptionWithRetry

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
