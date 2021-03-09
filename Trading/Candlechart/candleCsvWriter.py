import csv
import os.path
from datetime import datetime
from Trading.Candlechart.candle import CandleClassifier
import os
class CandleCsvWriter:
    def __init__(self, symbol, timeframe, path = '/home/doru/personal/trading/data/'):
        self.path = path + symbol+"-"+timeframe
        self.log_open_date = datetime.now()
        self.log_close_date = self.log_open_date

        if not os.path.isfile(self.path):
            self.__writeHeader()

    def __writeHeader(self):
        row=['Open', 'High', 'Low', 'Close', 'Date', 'Technical', 'Candlestick']
        self.__writeRow(row)

    def __writeRow(self, row):
        with open(self.path, 'a', newline='') as csvfile:
            spamwriter = csv.writer(csvfile, delimiter=',',
                                    quotechar='|', quoting=csv.QUOTE_MINIMAL)
            spamwriter.writerow(row)

    def writeCandle(self, candle):
        candle_data = candle.getData()
        row = [str(candle_data[0]), str(candle_data[1]), str(candle_data[2]), str(candle_data[3]), str(candle_data[4]), str(candle_data[5]), candle_data[6].pattern]

        if candle_data[4] < self.log_open_date:
            self.log_open_date = candle_data[4]
        elif candle_data[4] > self.log_close_date:
            self.log_close_date = candle_data[4]

        self.__writeRow(row)

    def __del__(self):
        path = os.path.abspath(self.path)

        # Turn open and close dates into strings
        log_open_date = self.log_open_date.strftime("%d_%m_%Y_%H.%M.%S")
        log_closing_date = self.log_close_date.strftime("%d_%m_%Y_%H.%M.%S")
        # Rename file to reflect open and close dates

        os.rename(path, path + "_from_" + log_open_date + "_to_" + log_closing_date +".csv")
        print("Closing csv writer")
