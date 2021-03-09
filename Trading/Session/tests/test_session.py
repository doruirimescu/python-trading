import pytest
import unittest
from unittest.mock import MagicMock
from Trading.Session.session import XTBSession

class TestClient:
    def login(self, uname, pwd, mode):
        pass
    def logout(self):
        pass
client = TestClient()
class TestSession(unittest.TestCase):

    def test_XTBSession(self):
        xtb = XTBSession(client)
        self.assertTrue(xtb is not None)

    def test_XTBSessionLogin(self):
        xtb = XTBSession(client)
        xtb.login('username', 'pwd')

    def test_XTBSessionLogout(self):
        xtb = XTBSession(client)
        xtb.logout()

    def test_XTBSessionLogoutCallsClientLogout(self):
        #Arrange
        client.logout = MagicMock()
        xtb =XTBSession(client)
        #Act
        xtb.logout()
        #Assert
        client.logout.assert_called_with()

    def test_XTBSessionDeleteCallsClientLogout(self):
        client.logout = MagicMock()
        xtb = XTBSession(client)
        del xtb
        client.logout.assert_called_with()

    def test_XTBSessionLoginReturnsClient(self):
        xtb = XTBSession(client)
        ret = xtb.login("","")
        self.assertTrue( ret == client)

    def test_XTBSessionLoginCallsClientLogin(self):
        #Arrange
        client.login = MagicMock()
        xtb =XTBSession(client)
        #Act
        xtb.login("","")
        #Assert
        client.login.assert_called_with("", "", mode='demo')
