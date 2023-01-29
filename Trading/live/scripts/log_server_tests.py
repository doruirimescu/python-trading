import getpass
import datetime
import time
from Trading.live.Logger.server_tester import *
from XTBApi.api import Client
import csv
from dotenv import load_dotenv
import os


def getTimeNowStr():
    return str(datetime.now())


def writeRow(path, row):
    with open(path, 'a', newline='') as csvfile:
        spamwriter = csv.writer(csvfile, delimiter=';',
                                quotechar='|', quoting=csv.QUOTE_MINIMAL)
        spamwriter.writerow(row)


if __name__ == '__main__':
    load_dotenv()
    username = os.getenv("XTB_USERNAME")
    password = os.getenv("XTB_PASSWORD")
    mode = 'demo'

    client = Client(username, password, mode)
    st = ServerTester(client)

    filename = "log/Server_test_results" + getTimeNowStr()+'.csv'
    writeRow(filename, ['Date', 'Status'])
    while True:
        response = st.test()
        print(response.error)
        writeRow(filename, [getTimeNowStr(), response.error])
        time.sleep(1)
    file_object.close()
