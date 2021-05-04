from datetime import datetime
from dataclasses import dataclass
import logging
#TODO: Use ExceptionWithRetry
__all = ['ServerTest', 'ServerTester']

@dataclass
class ServerTest:
    is_server_up: bool
    error: str

# create logger
logging.basicConfig(filename='example.log', encoding='utf-8', level=logging.INFO)
logger = logging.getLogger('Server tester')
logger.setLevel(logging.INFO)

class ServerTester:
    logger:logging
    def __init__(self, client):
        logger.info("Initialized Server Tester")
        self._client = client

    def test(self):
        try:
            logger.info("Try login")
            self._client.login()
        except Exception as e:
            logger.info("Login failed")
            return ServerTest(False, e.__str__() + " Login failed")

        try:
            logger.info("Try ping")
            self._client.ping()
        except Exception as e:
            logger.info("Ping failed")
            return ServerTest(False, e.__str__() + " Ping failed")

        logger.info("Test success")
        response = ServerTest(True, "Server up")
        return response
