from exception_with_retry import exception_with_retry

from Trading.live.client.client import XTBLoggingClient
from Trading.utils.send_email import send_email
from Trading.config.config import USERNAME, PASSWORD, MODE
from Trading.live.alert.alert import get_top_ten_biggest_swaps_report
from datetime import datetime
import os
import logging
from time import sleep


if __name__ == '__main__':

    FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=FORMAT)

    MAIN_LOGGER = logging.getLogger('Main logger')
    MAIN_LOGGER.setLevel(logging.DEBUG)
    MAIN_LOGGER.propagate = True

    client = XTBLoggingClient(USERNAME, PASSWORD, MODE, False)

    def monitor_once():
        subject = "Daily swap report " + str(datetime.now())
        body, data = get_top_ten_biggest_swaps_report(client)
        # send_email(subject, body)
        MAIN_LOGGER.info(body)

    monitor_once()
