import csv
import os.path
from datetime import datetime
from Trading.Candlechart.candle import CandleClassifier
from Trading.Instrument.instrument import Instrument
import os
class CandleCsvWriter:
    def __init__(self, instrument, path = '/home/doru/personal/trading/data/'):
        self.path = path + instrument.symbol+"-"+instrument.timeframe
        self.log_open_date = datetime.now()
        self.log_close_date = self.log_open_date

        if not os.path.isfile(self.path):
            self.__writeHeader()

    def __writeHeader(self):
        row=['Open', 'High', 'Low', 'Close', 'Date', 'Technical', 'Candlestick']
        self._writeRow(row)

    def _writeRow(self, row):
        with open(self.path, 'a', newline='') as csvfile:
            spamwriter = csv.writer(csvfile, delimiter=',',
                                    quotechar='|', quoting=csv.QUOTE_MINIMAL)
            spamwriter.writerow(row)

    def writeCandle(self, candle):
        candle_data = candle.getData()
        OPEN, HIGH, LOW, CLOSE, DATE, TECH, PAT = (0,1,2,3,4,5,6)
        row = [str(candle_data[OPEN]), str(candle_data[HIGH]), str(candle_data[LOW]),
                str(candle_data[CLOSE]), str(candle_data[DATE]), str(candle_data[TECH]), candle_data[PAT].pattern]

        if candle_data[DATE] < self.log_open_date:
            self.log_open_date = candle_data[DATE]
        elif candle_data[DATE] > self.log_close_date:
            self.log_close_date = candle_data[DATE]

        self._writeRow(row)

    def __del__(self):
        path = os.path.abspath(self.path)

        # Turn open and close dates into strings
        log_open_date = self.log_open_date.strftime("%d_%m_%Y_%H.%M.%S")
        log_closing_date = self.log_close_date.strftime("%d_%m_%Y_%H.%M.%S")
        # Rename file to reflect open and close dates

        os.rename(path, path + "_from_" + log_open_date + "_to_" + log_closing_date +".csv")
        print("Closing csv writer")
