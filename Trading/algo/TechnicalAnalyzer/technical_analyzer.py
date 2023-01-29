from Trading.algo.TechnicalAnalyzer.technical_analysis import TechnicalAnalysis
from Trading.algo.indicators.indicator_value_to_action import IndicatorValueToAction, IndicatorAction
from abc import ABC, abstractmethod
import numpy
import talib

class TechnicalAnalyzer(ABC):
    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    def analyse(self):
        pass

def RSI14(data: list):
    iva = IndicatorValueToAction(75,25,5)
    data = numpy.array(data)
    rsi = talib.RSI(data, timeperiod=14)
    action = iva.analyse(rsi[-1])
    print(rsi)
    return action

#TODO: Investigate this one
def STOCH9_6(data:list):
    data = numpy.array(data)
    #stoch = talib.STOCHF(high, low, close, fastd_period=9, fastk_period=6)

def MACD_12_26(data:list):
    data = numpy.array(data)
    macd = talib.MACD()

#TODO: Investigate this one
def ROC(data:list):
    data = numpy.array(data)
    talib.ROC(data)
