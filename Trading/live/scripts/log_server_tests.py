import getpass
import datetime
import time
from Trading.live.logger.server_tester import *
from XTBApi.api import client
import csv
from dotenv import load_dotenv
import os


def get_time_now_str():
    return str(datetime.now())


def write_row(path, row):
    with open(path, 'a', newline='') as csvfile:
        spamwriter = csv.writer(csvfile, delimiter=';',
                                quotechar='|', quoting=csv.QUOTE_MINIMAL)
        spamwriter.write_row(row)


if __name__ == '__main__':
    load_dotenv()
    username = os.getenv("XTB_USERNAME")
    password = os.getenv("XTB_PASSWORD")
    mode = 'demo'

    client = client(username, password, mode)
    st = ServerTester(client)

    filename = "log/Server_test_results" + get_time_now_str()+'.csv'
    write_row(filename, ['Date', 'Status'])
    while True:
        response = st.test()
        print(response.error)
        write_row(filename, [get_time_now_str(), response.error])
        time.sleep(1)
    file_object.close()
