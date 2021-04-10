import getpass
import datetime
import time
from Trading.Live.Logger.server_tester import *
from XTBApi.api import Client
import csv

def readUsername():
    f = open("username.txt", "r")
    lines = f.readlines()
    username = lines[0].rstrip()
    f.close()
    return username

def getTimeNowStr():
    return str(datetime.now())

def writeRow(path, row):
    with open(path, 'a', newline='') as csvfile:
        spamwriter = csv.writer(csvfile, delimiter=';',
                                quotechar='|', quoting=csv.QUOTE_MINIMAL)
        spamwriter.writerow(row)

if __name__ == '__main__':
    username = readUsername()
    password = getpass.getpass("XTB password:")
    mode = 'demo'

    client = Client(username, password, mode)
    st = ServerTester(client)

    filename = "Server_test_results" + getTimeNowStr()+'.csv'
    writeRow(filename, ['Date', 'Status'])
    while True:
        response = st.test()
        print(response.error)
        writeRow(filename, [getTimeNowStr(), response.error])
        time.sleep(1)
    file_object.close()
