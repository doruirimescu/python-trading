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
            date_time_obj = datetime.strptime(date[i], '%Y-%m-%d')
            print(date_time_obj.date())
            c = candle.Candle(open[i], high[i], low[i], close[i], date_time_obj.date())
            self.addCandle(c)

    def __initialize(self):
        self.candles_ = list()
        self.open = list()
        self.high = list()
        self.low = list()
        self.close = list()
        self.date = list()
        self.type_with_confidence_ = list()
        self.confidence=list()
        self.color = list()
        self.weekday = list()

    def addCandle(self, candle):
        self.candles_.append(candle)
        self.open.append(candle.open_)
        self.high.append(candle.high_)
        self.low.append(candle.low_)
        self.close.append(candle.close_)
        self.date.append(candle.date_)
        self.type_with_confidence_.append(candle.getTypeWithConfidence())
        self.color.append(candle.getColor())
        self.weekday.append(candle.getWeekday())

    def plot(self):
        arrow_list=[]
        counter=0
        for wd in self.weekday:
            candle_type_str = self.type_with_confidence_[counter].type.name
            candle_type_confidence = self.type_with_confidence_[counter].confidence
            annotation_text = candle_type_str + " " + str(candle_type_confidence) + "%"

            arrow=dict(x=self.date[counter],y=self.high[counter],xref="x",yref="y",text=annotation_text,ax=0,ay=-130,arrowhead = 3,
                arrowwidth=2.0,
                arrowcolor='rgb(0,0,250)',textangle=-90, font=dict(family='sans-serif', size=15))

            if candle_type_str is not 'UNDEFINED':
                arrow_list.append(arrow)
            counter +=1

        fig = go.Figure(data=[go.Candlestick(x=self.date,
                open=self.open,
                high=self.high,
                low=self.low,
                close=self.close,
                text =self.weekday)])
        fig.update_layout(title="Title", yaxis_title="Y title",annotations=arrow_list)

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


candlechart = CandleChart(df['AAPL.Open'], df['AAPL.High'], df['AAPL.Low'], df['AAPL.Close'], df['Date'] )
candlechart.plot()

import talib
num=talib.CDL3WHITESOLDIERS(df['AAPL.Open'], df['AAPL.High'], df['AAPL.Low'], df['AAPL.Close'])

for ind,val in enumerate(num):
    if val == 100:
        print(ind)
print(df['Date'][29])
