import unittest
from Trading.utils.argument_parser import CustomParser
import argparse
from unittest import mock


class TestArgumentParser(unittest.TestCase):
    @mock.patch('argparse.ArgumentParser.parse_args', return_value=argparse.Namespace(symbol="EURUSD", timeframe="1D"))
    def test_add_instrument(self, mock_args):
        cp = CustomParser("What this program does")
        cp.add_instrument()
        symbol, timeframe = cp.parse_args()
        self.assertEqual("EURUSD", symbol)
        self.assertEqual("1D", timeframe)

    @mock.patch('argparse.ArgumentParser.parse_args', return_value=argparse.Namespace(contract_value=1000))
    def test_add_contract_value(self, mock_args):
        cp = CustomParser("What this program does")
        cp.add_contract_value()
        contract_value, = cp.parse_args()
        self.assertEqual(1000, contract_value)

    @mock.patch('argparse.ArgumentParser.parse_args', return_value=argparse.Namespace(xtb_mode="demo"))
    def test_add_xtb_mode(self, mock_args):
        cp = CustomParser("What this program does")
        cp.add_xtb_mode()
        xtb_mode, = cp.parse_args()
        self.assertEqual("demo", xtb_mode)

    @mock.patch('argparse.ArgumentParser.parse_args', return_value=argparse.Namespace(xtb_username="username"))
    def test_add_xtb_username(self, mock_args):
        cp = CustomParser("What this program does")
        cp.add_xtb_username()
        xtb_username, = cp.parse_args()
        self.assertEqual("username", xtb_username)

    @mock.patch('argparse.ArgumentParser.parse_args', return_value=argparse.Namespace(xtb_password="pwd"))
    def test_add_xtb_password(self, mock_args):
        cp = CustomParser("What this program does")
        cp.add_xtb_password()
        xtb_password, = cp.parse_args()
        self.assertEqual("pwd", xtb_password)
