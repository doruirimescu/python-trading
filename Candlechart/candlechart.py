import candle
import datetime
import plotly.graph_objects as go

class CandleChart:
    def __init__(self, candles = list()):
        self.__initialize()
        self.candles_ = candles.copy()

        for candle in candles:
            print(candle)
            self.addCandle(candle)

    def __init__(self, open:list, high:list, low:list, close:list, date:list):
        self.__initialize()
        for i,v in open.items():
            c = candle.Candle(open[i], high[i], low[i], close[i], date[i])
            self.addCandle(c)

    def __initialize(self):
        self.candles_ = list()
        self.open = list()
        self.high = list()
        self.low = list()
        self.close = list()
        self.date = list()
        self.type = list()
        self.color = list()

    def addCandle(self, candle):
        self.candles_.append(candle)
        self.open.append(candle.open_)
        self.high.append(candle.high_)
        self.low.append(candle.low_)
        self.close.append(candle.close_)
        self.date.append(candle.date_)
        self.type.append(candle.getType().__repr__())
        self.color.append(candle.getColor())

    def plot(self):
        fig = go.Figure(data=[go.Candlestick(x=self.date,
                open=self.open,
                high=self.high,
                low=self.low,
                close=self.close,
                text =self.type)])
        fig.show()



# hammer = candle.Candle(0.7,1,0,0.9, datetime.date(2020,1,13))
# shaven_head = candle.Candle(0.8,1,0,0.99, datetime.date(2020,1,14))
# inverted_hammer = candle.Candle(0.3,1,0,0.1, datetime.date(2020,1,15))

# candlechart = CandleChart()
# candlechart.addCandle(hammer)
# candlechart.addCandle(shaven_head)
# candlechart.addCandle(inverted_hammer)
# candlechart.plot()

import plotly.graph_objects as go

import pandas as pd
from datetime import datetime

df = pd.read_csv('https://raw.githubusercontent.com/plotly/datasets/master/finance-charts-apple.csv')

df = df[1:10]

candlechart = CandleChart(df['AAPL.Open'], df['AAPL.High'], df['AAPL.Low'], df['AAPL.Close'], df['Date'] )
candlechart.plot()
