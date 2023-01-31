# import unittest
# from Trading.live.client.client import LoggingClient
# from unittest.mock import MagicMock


# class TestClient(unittest.TestCase):
#     def test_get_server_time(self):
#         client = MagicMock()
#         server_tester = MagicMock()
#         lc = LoggingClient(client, server_tester)
#         client.get_server_time.side_effect = ["time_response"]

#         response = lc.get_server_time()
#         self.assertEqual("time_response", response)

#         client.login.assert_called_once()
#         client.logout.assert_called_once()
