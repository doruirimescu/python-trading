import pytest
import unittest
from Trading.Live.Logger.server_tester import *
from unittest.mock import MagicMock

class MockClient:
    def __init__(self, uname, pwd, mode):
        pass

    def login(self):
        pass

    def logout(self):
        pass

    def get_lastn_candle_history(self, symbol, timeframe_in_seconds, number):
        if number == 10:
            raise Exception("Something wrong")
    def ping(self):
        pass

class TestServerTester(unittest.TestCase):
    def setUp(self):
        self.mock_client = MockClient("u", "p", "demo")

    def test_CreateTester(self):
        st = ServerTester(self.mock_client)
        self.assertTrue(True)

    def test_ServerIsUp(self):
        st = ServerTester(self.mock_client)
        response = st.test()
        self.assertTrue(response.is_server_up)
        self.assertEqual(response.error, "Server up")

    def test_ServerLoginFails(self):
        # Arrange
        raised_error = Exception('Login fails')
        self.mock_client.login =  MagicMock(side_effect = raised_error)
        st = ServerTester(self.mock_client)

        # Act
        response = st.test()

        # Assert
        self.assertFalse(response.is_server_up)
        self.assertEqual(type(response.error), str)
        self.assertEqual(response.error, raised_error.__str__() + " Login failed")

    def test_ServerPingFails(self):
        # Arrange
        raised_error = Exception('Ping fails')
        self.mock_client.ping =  MagicMock(side_effect = raised_error)
        st = ServerTester(self.mock_client)

        # Act
        response = st.test()

        # Assert
        self.assertFalse(response.is_server_up)
        self.assertEqual(type(response.error), str)
        self.assertEqual(response.error, raised_error.__str__() + " Ping failed")

if __name__ == '__main__':
    unittest.main()
