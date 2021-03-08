import csv
import os.path
from datetime import datetime
from candle import Candle

class CandleCsvWriter:
    def __init__(self, symbol, timeframe, candle, path = '/home/doru/personal/trading/data/'):
        self.path = path + symbol+"-"+timeframe+".csv"
        if not os.path.isfile(self.path):
            self.__writeHeader()

        candle_data = candle.getData()

        row = [str(candle_data[0]), str(candle_data[1]), str(candle_data[2]), str(candle_data[3]), str(candle_data[4]), str(candle_data[5]), candle_data[6].pattern]
        self.__writeRow(row)

    def __writeHeader(self):
        row=['Open', 'High', 'Low', 'Close', 'Date', 'Technical', 'Candlestick']
        self.__writeRow(row)

    def __writeRow(self, row):
        with open(self.path, 'a', newline='') as csvfile:
            spamwriter = csv.writer(csvfile, delimiter=',',
                                    quotechar='|', quoting=csv.QUOTE_MINIMAL)
            spamwriter.writerow(row)
