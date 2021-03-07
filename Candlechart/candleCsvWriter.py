import csv
import os.path
from datetime import datetime
from candle import Candle

class CandleCsvWriter:
    def __init__(self, symbol, timeframe, candle):
        self.path = '/home/doru/personal/trading/data/'+symbol+"-"+timeframe+".csv"
        if not os.path.isfile(self.path):
            self.__writeHeader()

        row = [str(candle.open_), str(candle.high_), str(candle.low_), str(candle.close_), str(candle.date_), candle.getTechnicalAnalysis(), candle.getCandlestickAnalysis()]
        self.__writeRow(row)

    def __writeHeader(self):
        row=['Open', 'High', 'Low', 'Close', 'Date', 'Technical', 'Pattern']
        self.__writeRow(row)

    def __writeRow(self, row):
        with open(self.path, 'a', newline='') as csvfile:
            spamwriter = csv.writer(csvfile, delimiter=',',
                                    quotechar='|', quoting=csv.QUOTE_MINIMAL)
            spamwriter.writerow(row)
