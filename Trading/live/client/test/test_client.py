import unittest
from Trading.live.client.client import get_cmd
from unittest.mock import MagicMock


class TestClient(unittest.TestCase):
    def test_get_cmd(self):
        result = get_cmd("buy")
        self.assertEqual(0, result)

        result = get_cmd("sell")
        self.assertEqual(1, result)

        result = get_cmd("BuY")
        self.assertEqual(0, result)

        result = get_cmd("SeLL")
        self.assertEqual(1, result)

        with self.assertRaises(ValueError):
            result = get_cmd("123")

#     def test_get_server_time(self):
#         client = MagicMock()
#         server_tester = MagicMock()
#         lc = LoggingClient(client, server_tester)
#         client.get_server_time.side_effect = ["time_response"]

#         response = lc.get_server_time()
#         self.assertEqual("time_response", response)

#         client.login.assert_called_once()
#         client.logout.assert_called_once()
